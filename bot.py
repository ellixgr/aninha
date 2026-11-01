#!/usr/bin/env python3
import asyncio
import os
import sys
import uuid
import time
import random
import requests
import json
import socket
import gc
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
from datetime import datetime, timedelta, timezone

# --- SERVIDOR HTTP KEEP-ALIVE PARA O RENDER ---
class SimpleHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"Bot is active and running!")

    def do_HEAD(self):
        self.send_response(200)
        self.end_headers()

def run_keep_alive_server():
    port = int(os.getenv("PORT", 10000))
    server = HTTPServer(('0.0.0.0', port), SimpleHandler)
    server.serve_forever()

threading.Thread(target=run_keep_alive_server, daemon=True).start()

# --- CONFIGURAÇÃO DE DNS PARA O MONGODB ---
RESOLV_CONF = "/etc/resolv.conf"
if not os.path.exists(RESOLV_CONF):
    os.makedirs("/data/data/com.termux/files/usr/etc", exist_ok=True)

try:
    import dns.resolver
    dns.resolver.default_resolver = dns.resolver.Resolver(configure=False)
    dns.resolver.default_resolver.nameservers = ['8.8.8.8', '1.1.1.1']
except ImportError:
    pass

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, CopyTextButton
from telegram.ext import (
    ApplicationBuilder, CommandHandler, CallbackQueryHandler,
    TypeHandler, ContextTypes, ApplicationHandlerStop, ChatMemberHandler,
    ChatJoinRequestHandler, MessageHandler, filters
)
from pymongo import MongoClient

# ==============================================
# ⚙️ CONFIGURAÇÕES GLOBAIS SEGURAS
# ==============================================
FUSO_RJ = timezone(timedelta(hours=-3))

GRUPO_VIP = int(os.getenv("GRUPO_VIP", "0"))
GRUPO_VIP_LINK = os.getenv("GRUPO_VIP_LINK", "")

GRUPO_ANUAL_ID = int(os.getenv("GRUPO_ANUAL_ID", str(GRUPO_VIP)))
GRUPO_ANUAL_LINK = os.getenv("GRUPO_ANUAL_LINK", GRUPO_VIP_LINK)

DONO_ID_GLOBAL = int(os.getenv("DONO_ID", "0"))
MP_TOKEN_COMUM = os.getenv("MP_TOKEN", "")

PLANOS_VIP_APENAS = {
    7.00:  (3600,     "⏳ 𝗩𝗜𝗣 𝗣𝗢𝗥 1 𝗛𝗢𝗥𝗔🔥",     GRUPO_VIP, GRUPO_VIP_LINK),
    12.00: (604800,   "📅 𝗩𝗜𝗣 𝗣𝗢𝗥 7 𝗗𝗜𝗔𝗦🔥🔥 (recomendado)",   GRUPO_VIP, GRUPO_VIP_LINK),
    29.90: (2592000,  "🗓️ 𝗩𝗜𝗣 𝗣𝗢𝗥 30 𝗗𝗜𝗔𝗦",      GRUPO_VIP, GRUPO_VIP_LINK),
    89.50: (31536000, "💎 𝗔𝗡𝗨𝗔𝗟 (𝗠𝗶𝗱𝗶𝗮𝘀 𝗿𝗮𝗿𝗮𝘀🤫𝗗𝗼𝘄𝗻𝗹𝗼𝗮𝗱𝘀 𝗹𝗶𝗯𝗲𝗿𝗮𝗱𝗼𝘀)", GRUPO_ANUAL_ID, GRUPO_ANUAL_LINK),
}

MENSAGEM_VIP = """‼️⚠️*ACESSO TOTALMENTE ANÔNIMO(A)*⚠️‼️

🔐 _+100 MIL MÍDIAS LIBERADAS_
🔥 _Conteúdos que viralizam e somem da internet_
💀 _Mídias raras e difíceis de encontrar_
🕯️ _Atualização constante_
📥 _Downloads liberados_
💋 _Famosas / Privacy / OnlyFans_
🫦 _Exclusivos selecionados_

👇 💎*Escolha seu plano, você não vai se arrepender*🤭🔥:"""

MIDIAS_BOT_1 = [
    "BAACAgEAAxkBAAINMWqHwstKPaNAoevtH_C8vbgx2rOiAAJ2BwAC2VFARLNksipNqGaVPQQ",
    "BAACAgEAAxkBAAINMmqHxQWRoW4M8dIocXIJgzoq6oDxAAJ6BwAC2VFARNbkIeRitsobPQQ",
    "BAACAgEAAxkBAAIUDGrSz4pByMyV8sm_i0CJKnA5CkK1AAJyDAACzV2ZRkBg1G5t867OPQQ"
]

MIDIAS_BOT_2 = [
    "BAACAgEAAxkBAAIBf2qHvh2A0w5UFXjXg9vd2xF_eLOsAAJ2BwAC2VFARDvn3nM8HjNGPQQ",
    "BAACAgEAAxkBAAIBgmqHviyF2CvcncX5wXtqlwABBfJfOgACdwcAAtlRQEQLGGpSxnBPoz0E"
]

BOTS_CONFIG = [
    {
        "nome": "aninha",
        "token": os.getenv("BOT_TOKEN_1", ""),
        "mp_token": MP_TOKEN_COMUM,
        "dono_id": DONO_ID_GLOBAL,
        "tipo_plano": "VIP",
        "midias": MIDIAS_BOT_1
    }
]

MONGO_URI = os.getenv("MONGO_URI", "")
if not MONGO_URI:
    print("❌ ERRO: A variável de ambiente MONGO_URI não foi configurada!")
    sys.exit(1)

try:
    mongo_client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=5000)
    mongo_client.admin.command('ping')
    db = mongo_client.get_database("bot_database")
    colecao_clientes = db["clientes"]
    colecao_bloqueados = db["bloqueados"]
    colecao_sistema = db["sistema_render"]
    print("✅ Conectado ao MongoDB com sucesso!")
except Exception as e:
    print(f"❌ ERRO ao conectar no MongoDB: {e}")
    sys.exit(1)

gc.enable()

def verificar_wifi():
    while True:
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            s.close()
            return True
        except Exception:
            time.sleep(10)

CANAL_DIVULGACAO_ID = -1004356555284
LEGENDA_DIVULGACAO = """⚠️😶‍🌫️ VIDEO COMPLETO NO GRUPO VIP🔥⚠️\n\nBÔNUS ⤵️ \n+20 𝗠𝗜𝗟 𝗠𝗜𝗗𝗜𝗔𝗦 𝗟𝗜𝗕𝗘𝗥𝗔𝗗𝗔𝗦✅"""

def carregar_bloqueados():
    try:
        return {doc["_id"]: doc for doc in colecao_bloqueados.find({})}
    except:
        return {}

def salvar_bloqueados(bloqueados):
    for uid, dados in bloqueados.items():
        colecao_bloqueados.update_one({"_id": uid}, {"$set": dados}, upsert=True)

def carregar_clientes():
    try:
        return {doc["_id"]: doc for doc in colecao_clientes.find({})}
    except:
        return {}

def salvar_clientes(clientes):
    for uid, dados in clientes.items():
        dados["_id"] = uid
        colecao_clientes.replace_one({"_id": uid}, dados, upsert=True)

def remover_cliente(uid):
    colecao_clientes.delete_one({"_id": str(uid)})

BLOQUEADOS = carregar_bloqueados()
AVISADO_HOJE = {}

def esta_bloqueado(uid):
    return str(uid) in BLOQUEADOS

def aviso_ja_enviado(uid):
    uid = str(uid)
    hoje = datetime.now().strftime("%Y-%m-%d")
    if AVISADO_HOJE.get(uid) == hoje: return True
    AVISADO_HOJE[uid] = hoje
    return False

MENSAGEM_BLOQUEADO = "🚫 VOCÊ FOI BLOQUEADO!\nContate o suporte: @Lyhhxv"

def log(bot_nome, tipo, mensagem):
    hora = datetime.now().strftime("%H:%M:%S")
    cor = {"USUARIO": "\033[94m", "VENDA": "\033[92m", "ERRO": "\033[91m", "SISTEMA": "\033[93m"}.get(tipo, "\033[97m")
    print(f"[{hora}] {cor}[{bot_nome}] [{tipo}] {mensagem}\033[0m")

def formatar_tempo_restante(segundos):
    if segundos <= 0: return "Expirado"
    if segundos >= 3153600000: return "♾️ VITALÍCIO"
    dias = int(segundos // 86400)
    horas = int((segundos % 86400) // 3600)
    minutos = int((segundos % 3600) // 60)
    partes = []
    if dias > 0: partes.append(f"{dias}d")
    if horas > 0: partes.append(f"{horas}h")
    if minutos > 0: partes.append(f"{minutos}m")
    return " ".join(partes) if partes else "Menos de 1m"

def formatar_data_rj(ts):
    if ts >= 3153600000: return "♾️ VITALÍCIO"
    return datetime.fromtimestamp(ts, tz=FUSO_RJ).strftime("%d/%m/%Y as %H:%M")

async def criar_e_iniciar_bot(bot_cfg, is_principal=False):
    token = bot_cfg["token"]
    mp_token = bot_cfg["mp_token"]
    dono_id = bot_cfg["dono_id"]
    lista_midias = bot_cfg["midias"]
    nome_bot = bot_cfg["nome"]    
    
    planos_usar = PLANOS_VIP_APENAS
    mensagem_inicial = MENSAGEM_VIP
    temp_add_cache = {}

    try:
        tmp_app = ApplicationBuilder().token(token).build()
        await tmp_app.initialize()
        bot_info = await tmp_app.bot.get_me()
        bot_username = bot_info.username
        await tmp_app.shutdown()
    except:
        bot_username = None

    if not token or ":" not in token:
        log(nome_bot, "ERRO", "TOKEN INVÁLIDO.")
        return

    clientes = carregar_clientes()
    LINK_BOTAO_START = f"https://t.me/{bot_username}?start=vip" if bot_username else GRUPO_VIP_LINK

    def eh_ativo(uid, clientes_atual=None):
        uid = str(uid)
        if uid == str(dono_id): return True
        c = (clientes_atual or clientes).get(uid, {})
        if not c: return False
        exp = c.get("expira_em", 0)
        if exp >= 3153600000: return True
        return exp > time.time()

    async def enviar_midia(bot_or_message, chat_id, midia_id, caption, reply_markup):
        is_photo = midia_id.startswith("AgAC") if midia_id else False
        try:
            if hasattr(bot_or_message, 'reply_video') or hasattr(bot_or_message, 'reply_photo'):
                if is_photo: await bot_or_message.reply_photo(midia_id, caption=caption, reply_markup=reply_markup, protect_content=True, parse_mode="Markdown")
                else: await bot_or_message.reply_video(midia_id, caption=caption, reply_markup=reply_markup, protect_content=True, parse_mode="Markdown")
            else:
                if is_photo: await bot_or_message.send_photo(chat_id, midia_id, caption=caption, reply_markup=reply_markup, protect_content=True, parse_mode="Markdown")
                else: await bot_or_message.send_video(chat_id, midia_id, caption=caption, reply_markup=reply_markup, protect_content=True, parse_mode="Markdown")
        except:
            if hasattr(bot_or_message, 'reply_text'):
                await bot_or_message.reply_text(caption, reply_markup=reply_markup, parse_mode="Markdown")
            else:
                await bot_or_message.send_message(chat_id, caption, reply_markup=reply_markup, parse_mode="Markdown")

    async def monitorar_entradas(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
        if not is_principal or not GRUPO_VIP: return
        result = update.chat_member
        if not result or update.effective_chat.id != GRUPO_VIP: return
        if result.new_chat_member.status == "member":
            uid = str(result.new_chat_member.user.id)
            if uid == str(dono_id) or result.new_chat_member.user.is_bot: return
            if not eh_ativo(uid):
                try:
                    await ctx.bot.ban_chat_member(chat_id=update.effective_chat.id, user_id=int(uid))
                    await ctx.bot.unban_chat_member(chat_id=update.effective_chat.id, user_id=int(uid))
                except: pass

    async def aprovar_solicitacao(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
        if not is_principal or not GRUPO_VIP: return
        req = update.chat_join_request
        if not req or update.effective_chat.id != GRUPO_VIP: return
        uid = str(req.from_user.id)
        if eh_ativo(uid):
            try: await req.approve()
            except: pass
        else:
            try: await req.decline()
            except: pass

    async def interceptar(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
        u = update.effective_user
        if not u: return
        uid = u.id
        if esta_bloqueado(uid): raise ApplicationHandlerStop
        if uid == dono_id: return

    async def start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
        if update.effective_chat.type != "private": return
        kb = [[InlineKeyboardButton(f"{nome} -> R$ {val:.2f}", callback_data=f"comprar_{val}")] for val, (_, nome, _, _) in planos_usar.items()]
        kb.append([InlineKeyboardButton("𝑷𝑹𝑬𝑽𝑰𝑨𝑺 𝑮𝑹𝑨𝑻𝑰𝑺🔥", url="https://t.me/+zL_k2splzuZiYTUx")])
        mid = random.choice(lista_midias) if lista_midias else None
        await enviar_midia(update.message, update.effective_chat.id, mid, mensagem_inicial, InlineKeyboardMarkup(kb))

    # ==============================================
    # 📋 FUNÇÃO DO COMANDO /MENU (EXIBE TODOS OS COMANDOS E SUAS FUNÇÕES)
    # ==============================================
    async def menu_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
        if update.effective_user.id != dono_id: return
        texto_menu = (
            "🤖 **PAINEL DE COMANDOS DO DONO** 👑\n\n"
            "📊 **Sistema e Banco de Dados:**\n"
            "• `/mongo` — Verifica o uso atual de RAM e estatísticas do MongoDB.\n"
            "• `/limparlixo` — Apaga cadastros expirados há mais de 30 dias para otimizar espaço.\n\n"
            "👥 **Gerenciamento de Clientes e VIPs:**\n"
            "• `/add ID` — Adiciona VIP manualmente ao usuário (abre botões para escolher o tempo: 1h, 7d, 30d ou Vitalício).\n"
            "• `/tirarvip ID` — Remove o status VIP e o cadastro do usuário do banco.\n"
            "• `/tirargrupo ID` — Bane e remove imediatamente o usuário do grupo VIP do Telegram.\n"
            "• `/enviarconvite` — Envia link do novo grupo para os clientes ativos que saíram, mantendo o histórico de tempo de onde pararam.\n"
            "• `/clientes` (ou `/clt`) — Lista todos os clientes ativos com detalhes de tempo restante e valores.\n\n"
            "📢 **Divulgação Automática:**\n"
            "• `/div` — Responda a uma foto/vídeo para disparar a divulgação padrão para o canal.\n"
            "• `/div2 [texto]` — Responda a uma foto/vídeo para disparar com texto personalizado.\n\n"
            "🛠️ **Moderação e Utilitários:**\n"
            "• `/block ID` — Bloqueia o usuário de interagir com o bot.\n"
            "• `/desbloquear ID` — Desbloqueia o usuário banido do bot.\n"
            "• `/ping` — Testa a latência de resposta do bot.\n"
            "• `/menu` — Exibe esta lista completa de comandos."
        )
        await update.message.reply_text(texto_menu, parse_mode="Markdown")

    async def mongo_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
        if update.effective_user.id != dono_id: return
        gc.collect()
        import psutil
        process = psutil.Process(os.getpid())
        ram_uso = process.memory_info().rss / 1024 / 1024
        db_stats = db.command("dbStats")
        tamanho_dados = db_stats.get("dataSize", 0) / 1024 / 1024
        total_clientes = colecao_clientes.count_documents({})
        total_bloqueados = colecao_bloqueados.count_documents({})
        expirados_antigos = colecao_clientes.count_documents({"expira_em": {"$lt": time.time() - 86400 * 30}})

        texto = (
            f"📊 **DIAGNÓSTICO DO SISTEMA & MONGO**\n\n"
            f"🧠 **Memória RAM Usada:** `{ram_uso:.2f} MB`\n"
            f"💾 **Tamanho do Banco (Mongo):** `{tamanho_dados:.2f} MB`\n"
            f"👥 **Clientes no Banco:** `{total_clientes}`\n"
            f"🚫 **Bloqueados:** `{total_bloqueados}`\n\n"
            f"🧹 **Lixo Detectado para Limpeza:**\n"
            f"• Cadastros expirados há > 30 dias: `{expirados_antigos}` registros\n\n"
            f"💡 Use `/limparlixo` para remover os registros antigos."
        )
        await update.message.reply_text(texto, parse_mode="Markdown")

    async def limparlixo_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
        if update.effective_user.id != dono_id: return
        res = colecao_clientes.delete_many({"expira_em": {"$lt": time.time() - 86400 * 30}})
        await update.message.reply_text(f"🧹 **Limpeza Concluída!**\nForam apagados `{res.deleted_count}` registros antigos e expirados do banco de dados.", parse_mode="Markdown")

    async def add_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
        if update.effective_user.id != dono_id: return
        args = ctx.args
        if len(args) < 1:
            await update.message.reply_text("⚠️ Uso correto: `/add ID_DO_USUARIO`", parse_mode="Markdown")
            return
        try:
            alvo_id = int(args[0])
        except:
            await update.message.reply_text("⚠️ ID inválido.")
            return

        temp_add_cache[update.effective_user.id] = alvo_id
        kb = [
            [InlineKeyboardButton("⏳ 1 Hora", callback_data="addt_3600"), InlineKeyboardButton("📅 7 Dias", callback_data="addt_604800")],
            [InlineKeyboardButton("🗓️ 30 Dias", callback_data="addt_2592000"), InlineKeyboardButton("💎 Vitalício", callback_data="addt_3153600000")],
            [InlineKeyboardButton("❌ Cancelar", callback_data="addt_cancel")]
        ]
        await update.message.reply_text(f"👤 Adicionando VIP para o ID: `{alvo_id}`\nEscolha o tempo de duração:", reply_markup=InlineKeyboardMarkup(kb), parse_mode="Markdown")

    async def tirarvip_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
        if update.effective_user.id != dono_id: return
        args = ctx.args
        if not args:
            await update.message.reply_text("⚠️ Uso: `/tirarvip ID`", parse_mode="Markdown")
            return
        uid = str(args[0])
        if uid in clientes:
            remover_cliente(uid)
            await update.message.reply_text(f"✅ Usuário `{uid}` removido do VIP com sucesso!", parse_mode="Markdown")
        else:
            await update.message.reply_text("⚠️ Este ID não consta como cliente ativo.")

    async def tirargrupo_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
        if update.effective_user.id != dono_id: return
        args = ctx.args
        if not args:
            await update.message.reply_text("⚠️ Uso: `/tirargrupo ID`", parse_mode="Markdown")
            return
        uid = int(args[0])
        try:
            await ctx.bot.ban_chat_member(chat_id=GRUPO_VIP, user_id=uid)
            await ctx.bot.unban_chat_member(chat_id=GRUPO_VIP, user_id=uid, only_if_banned=True)
            await update.message.reply_text(f"✅ Usuário `{uid}` foi removido do grupo VIP com sucesso!")
        except Exception as e:
            await update.message.reply_text(f"❌ Erro ao remover do grupo: {e}")

    async def enviarconvite_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
        if update.effective_user.id != dono_id: return
        msg_status = await update.message.reply_text("🔄 Verificando clientes ativos e enviando convites...")
        clientes_atual = carregar_clientes()
        enviados = 0
        
        for uid_str, cli in clientes_atual.items():
            if not eh_ativo(uid_str, clientes_atual): continue
            try:
                member = await ctx.bot.get_chat_member(chat_id=GRUPO_VIP, user_id=int(uid_str))
                if member.status in ['left', 'kicked']: raise Exception()
            except:
                try:
                    expira_em = cli.get("expira_em", 0)
                    restante = expira_em - time.time()
                    tempo_str = formatar_tempo_restante(restante)
                    await ctx.bot.send_message(
                        chat_id=int(uid_str),
                        text=f"⚠️ **Olá! Notamos que você não está no nosso grupo VIP atual.**\n\n"
                             f"Seu histórico foi mantido de onde parou!\n"
                             f"⏳ Seu tempo restante: **{tempo_str}**\n\n"
                             f"🔗 Entre no grupo oficial:\n👉 {GRUPO_VIP_LINK}",
                        parse_mode="Markdown"
                    )
                    enviados += 1
                    await asyncio.sleep(0.5)
                except: pass

        await msg_status.edit_text(f"✅ Processo concluído!\nConvites enviados para `{enviados}` clientes ativos que não estavam no grupo.", parse_mode="Markdown")

    async def clientes_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
        if update.effective_user.id != dono_id: return
        clientes_atual = carregar_clientes()
        agora = time.time()
        if not clientes_atual:
            await update.message.reply_text("📭 Nenhum cliente ativo.")
            return
        texto = f"📋 CLIENTES ATIVOS ({len(clientes_atual)}):\n\n"
        for idx, (uid, cli) in enumerate(clientes_atual.items(), 1):
            expira_em = cli.get("expira_em", 0)
            tempo_str = "♾️ VITALÍCIO" if expira_em >= 3153600000 else formatar_tempo_restante(expira_em - agora)
            data_limite = formatar_data_rj(expira_em)
            texto += f"🔹 {idx}. {cli.get('nome', 'Sem nome')}\n🆔 ID: {uid}\n👤 Usuário: {cli.get('username', 'Sem @')}\n💰 Valor: R$ {cli.get('valor_pago', 'Manual')}\n📅 Compra: {formatar_data_rj(cli.get('data_compra', time.time()))}\n⏳ Restante: {tempo_str}\n📆 Expira: {data_limite}\n👥 Grupo: {cli.get('grupo_link', GRUPO_VIP_LINK)}\n\n"
        await update.message.reply_text(texto)

    async def gerar_pag(valor, user):
        url = "https://api.mercadopago.com/v1/payments"
        headers = {"Authorization": f"Bearer {mp_token}", "Content-Type": "application/json", "X-Idempotency-Key": str(uuid.uuid4())}
        payload = {
            "transaction_amount": valor,
            "description": f"Acesso VIP R${valor:.2f}",
            "payment_method_id": "pix",
            "payer": {"email": f"u_{user.id}@bot.com", "first_name": user.first_name or "Cliente"}
        }
        try:
            r = requests.post(url, json=payload, headers=headers, timeout=15)
            if r.status_code == 201:
                d = r.json()
                qr = d.get("point_of_interaction", {}).get("transaction_data", {}).get("qr_code", "")
                return True, d["id"], qr
            return False, None, "Erro ao gerar PIX"
        except Exception as e:
            return False, None, str(e)

    async def verif_pag(pid):
        try:
            r = requests.get(f"https://api.mercadopago.com/v1/payments/{pid}", headers={"Authorization": f"Bearer {mp_token}"}, timeout=15)
            if r.status_code == 200:
                d = r.json()
                return d.get("status"), d.get("transaction_amount", 0)
            return "error", 0
        except:
            return "error", 0

    async def liberar_acesso(uid, val, user_obj, q_msg, ctx):
        plano = planos_usar.get(round(val, 2))
        seg = plano[0] if plano else 604800
        uid = str(uid)
        tempo_expira = time.time() + seg if seg < 3153600000 else 3153600000
        
        clientes_atual = carregar_clientes()
        clientes_atual[uid] = {
            "_id": uid,
            "nome": user_obj.first_name or "Cliente", 
            "username": f"@{user_obj.username}" if user_obj.username else "Sem @", 
            "expira_em": tempo_expira,
            "duracao_segundos": seg,
            "grupo": GRUPO_VIP, 
            "grupo_link": GRUPO_VIP_LINK, 
            "valor_pago": f"{val:.2f}",
            "data_compra": time.time()
        }
        salvar_clientes(clientes_atual)
        await q_msg.reply_text(f"✅ PAGAMENTO CONFIRMADO! 🎉\n\n🔗 Entre no grupo:\n👉 {GRUPO_VIP_LINK}")

    async def botoes(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
        q = update.callback_query
        d = q.data
        uid = str(update.effective_user.id)
        user = update.effective_user

        if d.startswith("addt_"):
            if update.effective_user.id != dono_id: return
            acao = d.split("_")[1]
            if acao == "cancel":
                await q.message.edit_text("❌ Operação cancelada.")
                return
            segundos = int(acao)
            alvo_id = temp_add_cache.get(update.effective_user.id)
            if not alvo_id:
                await q.message.edit_text("⚠️ Erro: Alvo não encontrado.")
                return
            
            tempo_expira = time.time() + segundos if segundos < 3153600000 else 3153600000
            clientes_atual = carregar_clientes()
            clientes_atual[str(alvo_id)] = {
                "_id": str(alvo_id),
                "nome": "Adicionado ADM",
                "username": "Manual",
                "expira_em": tempo_expira,
                "duracao_segundos": segundos,
                "grupo": GRUPO_VIP,
                "grupo_link": GRUPO_VIP_LINK,
                "valor_pago": "0.00",
                "data_compra": time.time()
            }
            salvar_clientes(clientes_atual)
            await q.message.edit_text(f"✅ VIP adicionado com sucesso para o ID `{alvo_id}`!", parse_mode="Markdown")
            return

        if d.startswith("comprar_"):
            v = float(d.split("_")[1])
            try: await q.message.delete()
            except: pass
            ok, pid, qr = await gerar_pag(v, user)
            if ok:
                kb = [
                    [InlineKeyboardButton("📋 Copiar Código", copy_text=CopyTextButton(qr))],
                    [InlineKeyboardButton("✅ Verificar Pagamento", callback_data=f"check_{pid}_{v}")],
                    [InlineKeyboardButton("⬅️ Voltar", callback_data="voltar")]
                ]
                await q.message.reply_text(f"✅ **PIX GERADO!**\n```\n{qr}\n```", reply_markup=InlineKeyboardMarkup(kb), parse_mode="Markdown")
            return

        elif d.startswith("check_"):
            partes = d.split("_")
            status, val_pago = await verif_pag(partes[1])
            if status == "approved":
                await q.answer("✅ APROVADO!", show_alert=True)
                await liberar_acesso(uid, float(partes[2]), user, q.message, ctx)
            else:
                await q.answer("⏳ Não aprovado ainda.", show_alert=True)
            return

        elif d == "voltar":
            try: await q.message.delete()
            except: pass
            kb = [[InlineKeyboardButton(f"{nome} -> R$ {val:.2f}", callback_data=f"comprar_{val}")] for val, (_, nome, _, _) in planos_usar.items()]
            await enviar_midia(ctx.bot, int(uid), random.choice(lista_midias) if lista_midias else None, mensagem_inicial, InlineKeyboardMarkup(kb))
            return

    try:
        app = ApplicationBuilder().token(token).build()
        app.add_handler(TypeHandler(Update, interceptar), group=-1)
        
        # 📋 REGISTRO DE TODOS OS COMANDOS DO BOT (INCLUINDO O /menu)
        app.add_handler(CommandHandler("start", start))
        app.add_handler(CommandHandler("menu", menu_cmd))
        app.add_handler(CommandHandler("mongo", mongo_cmd))
        app.add_handler(CommandHandler("limparlixo", limparlixo_cmd))
        app.add_handler(CommandHandler("add", add_cmd))
        app.add_handler(CommandHandler("tirarvip", tirarvip_cmd))
        app.add_handler(CommandHandler("tirargrupo", tirargrupo_cmd))
        app.add_handler(CommandHandler("enviarconvite", enviarconvite_cmd))
        app.add_handler(CommandHandler("clientes", clientes_cmd))
        app.add_handler(CommandHandler("clt", clientes_cmd))
        
        app.add_handler(CallbackQueryHandler(botoes))
        
        if is_principal and GRUPO_VIP:
            app.add_handler(ChatMemberHandler(monitorar_entradas, ChatMemberHandler.CHAT_MEMBER))
            app.add_handler(ChatJoinRequestHandler(aprovar_solicitacao))

        log(nome_bot, "SISTEMA", "✅ BOT ONLINE!")
        await app.initialize()
        await app.start()
        await app.updater.start_polling(drop_pending_updates=False)
        while True:
            verificar_wifi()
            await asyncio.sleep(60)
    except Exception as e:
        log(nome_bot, "ERRO", f"❌ FALHA: {e}")

async def main():
    for idx, bot_cfg in enumerate(BOTS_CONFIG):
        if idx > 0: await asyncio.sleep(3)      
        asyncio.create_task(criar_e_iniciar_bot(bot_cfg, is_principal=(idx == 0)))
    while True: await asyncio.sleep(3600)

if __name__ == "__main__":
    while True:
        try: asyncio.run(main())
        except KeyboardInterrupt: break
        except Exception: time.sleep(5)
