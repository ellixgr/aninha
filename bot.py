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
from datetime import datetime, timedelta

# --- REGISTRO DO TEMPO DE INÍCIO DA APLICAÇÃO ---
TEMPO_INICIAL_BOT = time.time()

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

# Iniciar o servidor web em segundo plano para manter o Render acordado
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
from config import (
    BOTS_CONFIG, GRUPO_VIP, GRUPO_VIP_LINK,
    FUSO_RJ, PLANOS_VIP_APENAS, MENSAGEM_VIP
)

# ==============================================
# 🔗 CONEXÃO COM O MONGODB (VIA VARIÁVEL DE AMBIENTE)
# ==============================================
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
GRUPO_ORIGEM_VIP_ID = None

LEGENDA_DIVULGACAO = """⚠️😶‍🌫️ VIDEO COMPLETO NO GRUPO VIP🔥⚠️

BÔNUS ⤵️ 
+20 𝗠𝗜𝗟 𝗠𝗜𝗗𝗜𝗔𝗦 𝗟𝗜𝗕𝗘𝗥𝗔𝗗𝗔𝗦✅
𝗠𝗶𝗱𝗶𝗮𝘀 𝗿𝗮𝗿𝗮𝘀 𝗲 𝗱𝗶𝗳𝗶𝗰𝗲𝗶𝘀 𝗱𝗲 𝗲𝗻𝗰𝗼𝗻𝘁𝗿𝗮𝗿💎
𝗗𝗼𝘄𝗻𝗹𝗼𝗮𝗱𝘀 liberados☑️"""

def carregar_bloqueados():
    try:
        docs = colecao_bloqueados.find({})
        return {doc["_id"]: doc for doc in docs}
    except Exception as e:
        print(f"ERRO LER BLOQUEADOS: {e}")
        return {}

def salvar_bloqueados(bloqueados):
    try:
        for uid, dados in bloqueados.items():
            colecao_bloqueados.update_one(
                {"_id": uid},
                {"$set": dados},
                upsert=True
            )
    except Exception as e:
        print(f"ERRO SALVAR BLOQUEADOS: {e}")

def carregar_clientes():
    try:
        docs = colecao_clientes.find({})
        return {doc["_id"]: doc for doc in docs}
    except Exception as e:
        print(f"ERRO LER CLIENTES: {e}")

def salvar_clientes(clientes):
    try:
        for uid, dados in clientes.items():
            dados["_id"] = uid
            colecao_clientes.replace_one({"_id": uid}, dados, upsert=True)
    except Exception as e:
        print(f"ERRO SALVAR CLIENTES: {e}")

def remover_cliente(uid):
    try:
        colecao_clientes.delete_one({"_id": str(uid)})
    except Exception as e:
        print(f"ERRO REMOVER CLIENTE: {e}")

BLOQUEADOS = carregar_bloqueados()
AVISADO_HOJE = {}

def esta_bloqueado(uid):
    return str(uid) in BLOQUEADOS

def aviso_ja_enviado(uid):
    uid = str(uid)
    hoje = datetime.now().strftime("%Y-%m-%d")
    if AVISADO_HOJE.get(uid) == hoje:
        return True
    AVISADO_HOJE[uid] = hoje
    return False

MENSAGEM_BLOQUEADO = """🚫 VOCÊ FOI BLOQUEADO!
Motivo: Floodar / sobrecarregar o sistema.

Se acha que foi engano, fale com o suporte:
📞 @Lyhhxv

Não crie novas contas — serão bloqueadas também.
"""

def log(bot_nome, tipo, mensagem):
    hora = datetime.now().strftime("%H:%M:%S")
    cor = {
        "USUARIO": "\033[94m", "VENDA": "\033[92m", "ERRO": "\033[91m",
        "SISTEMA": "\033[93m", "AVISO": "\033[95m", "BLOQUEIO": "\033[90m",
        "CHAT": "\033[96m"
    }.get(tipo, "\033[97m")
    reset = "\033[0m"
    print(f"[{hora}] {cor}[{bot_nome}] [{tipo}] {mensagem}{reset}")

def formatar_tempo_restante(segundos):
    if segundos <= 0: return "Expirado"
    if segundos >= 3153600000: return "♾️ VITALÍCIO"
    if segundos >= 31536000: return "1 Ano"
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
    ULTIMO_COMANDO = {}
    CONTADOR_AVISOS_FLOD = {}
    BLOQUEIO_FLOD = {}
    TEMPO_LIMITE_COMANDO = 2
    MAX_AVISOS_FLOD = 5
    TEMPO_BLOQUEIO_FLOD = 600
    msgs_para_apagar = {}
    
    try:
        tmp_app = ApplicationBuilder().token(token).build()
        await tmp_app.initialize()
        bot_info = await tmp_app.bot.get_me()
        bot_username = bot_info.username
        await tmp_app.shutdown()
    except:
        bot_username = None

    if not token or ":" not in token or len(token) < 30:
        log(nome_bot, "ERRO", f"TOKEN INVÁLIDO OU NÃO DEFINIDO NAS VARIÁVEIS DE AMBIENTE.")
        return
    log(nome_bot, "SISTEMA", f"✅ INICIANDO — {'[PRINCIPAL]' if is_principal else '[VENDEDOR]'}")
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
            if not midia_id:
                raise ValueError("ID de mídia vazio/inválido")
            if hasattr(bot_or_message, 'reply_video') or hasattr(bot_or_message, 'reply_photo'):
                if is_photo:
                    await bot_or_message.reply_photo(midia_id, caption=caption, reply_markup=reply_markup, protect_content=True, parse_mode="Markdown")
                else:
                    await bot_or_message.reply_video(midia_id, caption=caption, reply_markup=reply_markup, protect_content=True, parse_mode="Markdown")
            else:
                if is_photo:
                    await bot_or_message.send_photo(chat_id, midia_id, caption=caption, reply_markup=reply_markup, protect_content=True, parse_mode="Markdown")
                else:
                    await bot_or_message.send_video(chat_id, midia_id, caption=caption, reply_markup=reply_markup, protect_content=True, parse_mode="Markdown")
        except Exception as e:
            log(nome_bot, "ERRO", f"Falha ao enviar mídia ({e}). Enviando texto...")
            try:
                if hasattr(bot_or_message, 'reply_text'):
                    await bot_or_message.reply_text(caption, reply_markup=reply_markup, parse_mode="Markdown")
                else:
                    await bot_or_message.send_message(chat_id, caption, reply_markup=reply_markup, parse_mode="Markdown")
            except Exception as e2:
                log(nome_bot, "ERRO", f"Falha final ao responder {chat_id}: {e2}")

    async def monitorar_entradas(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
        if not is_principal or GRUPO_VIP is None: return
        result = update.chat_member
        if not result: return
        chat_id = update.effective_chat.id
        if chat_id != GRUPO_VIP:
            return
        status_novo = result.new_chat_member.status
        if status_novo in ["member"]:
            uid = str(result.new_chat_member.user.id)
            nome_usuario = result.new_chat_member.user.first_name or "Sem nome"          
            if uid == str(dono_id) or result.new_chat_member.user.is_bot:
                return
            clientes_atual = carregar_clientes()
            if not eh_ativo(uid, clientes_atual):
                log(nome_bot, "SISTEMA", f"🚫 REMOVENDO INVASOR — {nome_usuario} | ID:{uid}")
                try:
                    await ctx.bot.ban_chat_member(chat_id=chat_id, user_id=int(uid))
                    await ctx.bot.unban_chat_member(chat_id=chat_id, user_id=int(uid))
                    log(nome_bot, "SISTEMA", f"✅ INVASOR REMOVIDO — ID:{uid}")
                except Exception as e:
                    log(nome_bot, "ERRO", f"❌ ERRO AO KICKAR: {e}")
        
    async def aprovar_solicitacao(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
        if not is_principal or GRUPO_VIP is None: return
        req = update.chat_join_request
        if not req: return
        chat_id = update.effective_chat.id
        if chat_id != GRUPO_VIP:
            return
        uid = str(req.from_user.id)
        clientes_atual = carregar_clientes()        
        try:
            if eh_ativo(uid, clientes_atual):
                log(nome_bot, "SISTEMA", f"✅ APROVANDO ENTRADA — {req.from_user.first_name} | ID:{uid}")
                
                cli = clientes_atual.get(uid, {})
                duracao_original = cli.get("duracao_segundos", 0)
                if duracao_original > 0 and duracao_original < 3153600000:
                    novo_tempo_expira = time.time() + duracao_original
                    cli["expira_em"] = novo_tempo_expira
                    cli["data_entrada_grupo"] = time.time()
                    salvar_clientes(clientes_atual)
                    log(nome_bot, "SISTEMA", f"⏳ Contagem iniciada para {req.from_user.first_name} a partir da entrada!")

                await req.approve()
            else:
                log(nome_bot, "BLOQUEIO", f"🚫 RECUSANDO ENTRADA — {req.from_user.first_name} | ID:{uid}")
                await req.decline()
        except Exception as e:
            if "Hide_requester_missing" in str(e) or "USER_ALREADY_PART" in str(e):
                pass
            else:
                log(nome_bot, "ERRO", f"Erro no join request: {e}")

    async def log_mensagens(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
        if update.message and update.message.text:
            u = update.effective_user
            nome = u.first_name if u else "Desconhecido"
            uid = u.id if u else "0"
            texto = update.message.text
            log(nome_bot, "CHAT", f"MSG de {nome} (ID: {uid}): {texto}")

    async def interceptar(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
        u = update.effective_user
        if not u: return
        uid = u.id
        agora = time.time()
        if esta_bloqueado(uid):
            if not aviso_ja_enviado(uid):
                try: await ctx.bot.send_message(update.effective_chat.id, MENSAGEM_BLOQUEADO)
                except: pass
            log(nome_bot, "BLOQUEIO", f"🚫 BLOQUEADO TENTOU INTERAGIR — ID:{uid}")
            raise ApplicationHandlerStop

        if uid == dono_id: return
        COMANDOS_LIBERADOS = ['/start', '/suporte', '/suport', '/meu_id', '/block', '/desbloquear', '/div', '/div2', '/menu', '/ping', '/pin']
        if update.message and update.message.text and update.message.text.startswith('/'):
            cmd = update.message.text.split()[0].split('@')[0].lower()
            if cmd in COMANDOS_LIBERADOS:
                if cmd in ['/div', '/div2', '/menu', '/ping', '/pin']:
                    raise ApplicationHandlerStop
                
                if uid not in ULTIMO_COMANDO: ULTIMO_COMANDO[uid] = {}
                ultimo = ULTIMO_COMANDO[uid].get(cmd, 0)
                if agora - ultimo < TEMPO_LIMITE_COMANDO:
                    CONTADOR_AVISOS_FLOD[uid] = CONTADOR_AVISOS_FLOD.get(uid, 0) + 1
                    if CONTADOR_AVISOS_FLOD[uid] >= MAX_AVISOS_FLOD:
                        BLOQUEIO_FLOD[uid] = agora + TEMPO_BLOQUEIO_FLOD
                        CONTADOR_AVISOS_FLOD[uid] = 0
                        await ctx.bot.send_message(update.effective_chat.id, "🚫 Bloqueado por floodar! Tente em 10 min.")
                        raise ApplicationHandlerStop
                    await ctx.bot.send_message(update.effective_chat.id, "⚠️ Não envie muitos comandos seguidos.")
                    raise ApplicationHandlerStop
                ULTIMO_COMANDO[uid][cmd] = agora
                return
            raise ApplicationHandlerStop

    async def start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
        if update.effective_chat.type != "private": return
        u = update.effective_user

        kb = []
        for valor, (seg, nome_plano, grupo_id, grupo_link) in planos_usar.items():
            kb.append([InlineKeyboardButton(f"{nome_plano} -> R$ {valor:.2f}", callback_data=f"comprar_{valor}")])
        kb.append([InlineKeyboardButton("𝑷𝑹𝑬𝑽𝑰𝑨𝑺 𝑮𝑹𝑨𝑻𝑰𝑺🔥", url="https://t.me/+zL_k2splzuZiYTUx")])

        mid = random.choice(lista_midias) if lista_midias else None
        await enviar_midia(update.message, update.effective_chat.id, mid, mensagem_inicial, InlineKeyboardMarkup(kb))

    async def ping_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
        if update.effective_user.id != dono_id: return
        inicio = time.time()
        msg = await update.message.reply_text("🏓 Calculando ping...")
        fim = time.time()
        latencia = int((fim - inicio) * 1000)
        await msg.edit_text(f"🏓 **PONG!**\n⚡ Latência: **{latencia}ms**")

    async def pin_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
        if update.effective_user.id != dono_id: return
        
        agora = time.time()
        tempo_ligado_seg = agora - TEMPO_INICIAL_BOT
        
        horas_ligado = int(tempo_ligado_seg // 3600)
        minutos_ligado = int((tempo_ligado_seg % 3600) // 60)
        
        # Limite total do Render gratuito: 750 horas por mês
        horas_totais_render = 750
        horas_restantes = max(0, horas_totais_render - (tempo_ligado_seg / 3600))
        
        # Data/Hora aproximada em que as 750 horas se esgotam a partir do início
        data_desligamento = datetime.now(FUSO_RJ) + timedelta(seconds=(750 * 3600 - tempo_ligado_seg))
        data_desligamento_str = data_desligamento.strftime("%d/%m/%Y às %H:%M")

        texto = (
            f"📊 **STATUS DE EXECUÇÃO (RENDER)**\n\n"
            f"⏱️ **Tempo ligado:** {horas_ligado}h {minutos_ligado}m\n"
            f"⏳ **Quota mensal Render:** {horas_totais_render}h (Plano Gratuito)\n"
            f"📉 **Horas restantes do plano:** ~{horas_restantes:.1f}h\n"
            f"🛑 **Previsão de término da quota:** {data_desligamento_str}"
        )
        await update.message.reply_text(texto, parse_mode="Markdown")

    async def div_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
        if update.effective_user.id != dono_id: return
        msg = update.message
        reply = msg.reply_to_message
        
        if not reply or not (reply.video or reply.photo):
            await msg.reply_text("⚠️ Responda a uma foto ou a um vídeo com o comando /div")
            return

        botao = InlineKeyboardMarkup([[InlineKeyboardButton("🔥 ENTRAR AGORA 🔥", url=LINK_BOTAO_START)]])
        
        try:
            if reply.video:
                await ctx.bot.send_video(
                    chat_id=CANAL_DIVULGACAO_ID,
                    video=reply.video.file_id,
                    caption=LEGENDA_DIVULGACAO,
                    reply_markup=botao,
                    protect_content=True,
                    parse_mode="Markdown"
                )
            elif reply.photo:
                await ctx.bot.send_photo(
                    chat_id=CANAL_DIVULGACAO_ID,
                    photo=reply.photo[-1].file_id,
                    caption=LEGENDA_DIVULGACAO,
                    reply_markup=botao,
                    protect_content=True,
                    parse_mode="Markdown"
                )
            await msg.reply_text("✅ Divulgação enviada com sucesso!")
        except Exception as e:
            await msg.reply_text(f"❌ Erro ao enviar divulgação: {e}")

    async def div2_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
        if update.effective_user.id != dono_id: return
        msg = update.message
        reply = msg.reply_to_message
        
        texto_custom = " ".join(ctx.args)
        if not texto_custom:
            await msg.reply_text("⚠️ Uso correto: /div2 [Sua mensagem aqui] (respondendo a uma foto ou vídeo)")
            return

        if not reply or not (reply.video or reply.photo):
            await msg.reply_text("⚠️ Responda a uma foto ou a um vídeo junto com o comando /div2")
            return

        botao = InlineKeyboardMarkup([[InlineKeyboardButton("🔥 ENTRAR AGORA 🔥", url=LINK_BOTAO_START)]])
        
        try:
            if reply.video:
                await ctx.bot.send_video(
                    chat_id=CANAL_DIVULGACAO_ID,
                    video=reply.video.file_id,
                    caption=texto_custom,
                    reply_markup=botao,
                    protect_content=True,
                    parse_mode="Markdown"
                )
            elif reply.photo:
                await ctx.bot.send_photo(
                    chat_id=CANAL_DIVULGACAO_ID,
                    photo=reply.photo[-1].file_id,
                    caption=texto_custom,
                    reply_markup=botao,
                    protect_content=True,
                    parse_mode="Markdown"
                )
            await msg.reply_text("✅ Divulgação personalizada enviada com sucesso!")
        except Exception as e:
            await msg.reply_text(f"❌ Erro ao enviar divulgação: {e}")

    async def menu_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
        if update.effective_user.id != dono_id: return
        
        texto_menu = (
            "🤖 PAINEL DE COMANDOS DO DONO\n\n"
            "📢 Divulgação:\n"
            "• /div — Envia mídia com legenda padrão.\n"
            "• /div2 [texto] — Envia mídia com texto personalizado.\n\n"
            "👥 Gerenciamento:\n"
            "• /clientes ou /clt — Lista todos os clientes ativos.\n\n"
            "🔒 Moderação:\n"
            "• /block [ID] — Bloqueia usuário.\n"
            "• /desbloquear [ID] — Desbloqueia usuário.\n\n"
            "🛠️ Utilitários:\n"
            "• /ping — Mostra a latência do bot.\n"
            "• /pin — Mostra o tempo ligado e quota do Render.\n"
            "• /pegarid — Copia o file_id de uma mídia.\n"
            "• /meu_id — Mostra seu ID.\n"
            "• /suporte — Contato de suporte.\n"
            "• /menu — Exibe este painel."
        )
        await update.message.reply_text(texto_menu)

    async def block_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
        if update.effective_user.id != dono_id: return
        args = ctx.args
        if not args:
            await update.message.reply_text("⚠️ Uso: /block {id}")
            return
        try: uid_alvo = str(int(args[0]))
        except:
            await update.message.reply_text("⚠️ ID inválido!")
            return
        if uid_alvo == str(dono_id):
            await update.message.reply_text("⚠️ Não pode bloquear o dono!")
            return
        global BLOQUEADOS
        BLOQUEADOS[uid_alvo] = {"motivo": "Bloqueado pelo dono", "bloqueado_em": time.time()}
        salvar_bloqueados(BLOQUEADOS)
        log(nome_bot, "BLOQUEIO", f"🚫 USUÁRIO {uid_alvo} BLOQUEADO!")
        await update.message.reply_text(f"✅ USUÁRIO {uid_alvo} BLOQUEADO!")

    async def desbloquear_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
        if update.effective_user.id != dono_id: return
        args = ctx.args
        if not args:
            await update.message.reply_text("⚠️ Uso: /desbloquear {id}")
            return
        try: uid_alvo = str(int(args[0]))
        except:
            await update.message.reply_text("⚠️ ID inválido!")
            return
        global BLOQUEADOS
        if uid_alvo in BLOQUEADOS:
            del BLOQUEADOS[uid_alvo]
            salvar_bloqueados(BLOQUEADOS)
            log(nome_bot, "BLOQUEIO", f"🔓 USUÁRIO {uid_alvo} DESBLOQUEADO!")
            await update.message.reply_text(f"✅ USUÁRIO {uid_alvo} DESBLOQUEADO!")
        else:
            await update.message.reply_text(f"⚠️ Não está bloqueado.")

    async def meu_id_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
        uid = str(update.effective_user.id)
        texto = f"🆔 SEU ID:\n\n<code>{uid}</code>"
        kb = [[InlineKeyboardButton("📋 COPIAR", copy_text=CopyTextButton(uid))]]
        await update.message.reply_text(texto, reply_markup=InlineKeyboardMarkup(kb), parse_mode="HTML")

    async def suporte_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
        await update.message.reply_text("📞 SUPORTE:\n\nContate: @Lyhhxv")

    async def pegarid_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
        if update.effective_user.id != dono_id: return
        mensagem = update.message
        file_id = None
        if mensagem.reply_to_message:
            if mensagem.reply_to_message.video: file_id = mensagem.reply_to_message.video.file_id
            elif mensagem.reply_to_message.document: file_id = mensagem.reply_to_message.document.file_id
            elif mensagem.reply_to_message.photo: file_id = mensagem.reply_to_message.photo[-1].file_id
        elif mensagem.video: file_id = mensagem.video.file_id
        elif mensagem.document: file_id = mensagem.document.file_id
        elif mensagem.photo: file_id = mensagem.photo[-1].file_id
        if not file_id:
            await mensagem.reply_text("⚠️ Responda um vídeo ou foto com /pegarid")
            return
        texto = f"✅ FILE_ID:\n\n<code>{file_id}</code>"
        kb = [[InlineKeyboardButton("📋 COPIAR", copy_text=CopyTextButton(file_id))]]
        await mensagem.reply_text(texto, reply_markup=InlineKeyboardMarkup(kb), parse_mode="HTML")

    async def expurgar_expirados(bot_instancia):
        if not is_principal: return 0
        agora = time.time()
        removidos_count = 0

        log(nome_bot, "AVISO", f"🔍 CHECAGEM DE EXPIRADOS — Verificando...")
        
        clientes_atual = carregar_clientes()
        
        for uid_str in list(clientes_atual.keys()):
            cli = clientes_atual[uid_str]
            exp = cli.get("expira_em", 0)
            
            if exp >= 3153600000:
                continue
            if exp > agora:
                continue

            grupo_id = cli.get("grupo") or GRUPO_VIP
            if not grupo_id:
                log(nome_bot, "ERRO", f"❌ ID do grupo vazio para o cliente {uid_str}")
                continue

            log(nome_bot, "AVISO", f"🚨 ID:{uid_str} EXPIRADO! Removendo do grupo...")
            
            try:
                chat_id_num = int(grupo_id)
                user_id_num = int(uid_str)
                
                await bot_instancia.ban_chat_member(chat_id=chat_id_num, user_id=user_id_num)
                await bot_instancia.unban_chat_member(chat_id=chat_id_num, user_id=user_id_num, only_if_banned=True)
                
                remover_cliente(uid_str)
                removidos_count += 1
                log(nome_bot, "SISTEMA", f"✅ REMOVIDO — ID:{uid_str}")
                    
            except Exception as e:
                log(nome_bot, "ERRO", f"❌ Erro ao banir {uid_str}: {e}")
        
        del clientes_atual
        gc.collect()
        return removidos_count

    async def clientes_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
        if update.effective_user.id != dono_id: return
        if is_principal:
            await expurgar_expirados(ctx.bot)
            
        clientes_atual = carregar_clientes()
        agora = time.time()
        if not clientes_atual:
            await update.message.reply_text("📭 Nenhum cliente ativo.")
            return
        texto = f"📋 CLIENTES ATIVOS ({len(clientes_atual)}):\n\n"
        for idx, (uid, cli) in enumerate(clientes_atual.items(), 1):
            expira_em = cli.get("expira_em", 0)
            if expira_em >= 3153600000:
                tempo_str = "♾️ VITALÍCIO"
                data_limite = "♾️ VITALÍCIO"
            else:
                tempo_restante = expira_em - agora
                tempo_str = formatar_tempo_restante(tempo_restante)
                data_limite = formatar_data_rj(expira_em)
            nome = cli.get("nome", "Sem nome")
            username = cli.get("username", "Sem @")
            grupo_link = cli.get("grupo_link", GRUPO_VIP_LINK)
            valor = cli.get("valor_pago", "Sem registro")
            data_compra = formatar_data_rj(cli.get("data_compra")) if cli.get("data_compra") else "Sem registro"
            texto += f"🔹 {idx}. {nome}\n🆔 ID: {uid}\n👤 Usuário: {username}\n💰 Valor: R$ {valor}\n📅 Compra: {data_compra}\n⏳ Restante: {tempo_str}\n📆 Expira: {data_limite}\n👥 Grupo: {grupo_link}\n\n"
        await update.message.reply_text(texto)

    async def gerar_pag(valor, user):
        log(nome_bot, "USUARIO", f"Gerando PIX — User:{user.id} Valor:R${valor}")
        url = "https://api.mercadopago.com/v1/payments"
        headers = {"Authorization": f"Bearer {mp_token}", "Content-Type": "application/json", "X-Idempotency-Key": str(uuid.uuid4())}
        payload = {
            "transaction_amount": valor,
            "description": f"Acesso VIP R${valor:.2f}",
            "payment_method_id": "pix",
            "payer": {"email": f"u_{user.id}@bot.com", "first_name": user.first_name or "Cliente", "last_name": user.last_name or "Telegram"}
        }
        try:
            r = requests.post(url, json=payload, headers=headers, timeout=15)
            if r.status_code == 201:
                d = r.json()
                qr = d.get("point_of_interaction", {}).get("transaction_data", {}).get("qr_code", "")
                return True, d["id"], qr
            return False, None, f"Erro {r.status_code}: {r.text[:80]}"
        except Exception as e:
            log(nome_bot, "ERRO", f"Exceção gerar PIX: {e}")
            return False, None, f"Erro de conexão: {str(e)[:80]}"

    async def verif_pag(pid):
        url = f"https://api.mercadopago.com/v1/payments/{pid}"
        headers = {"Authorization": f"Bearer {mp_token}"}
        try:
            r = requests.get(url, headers=headers, timeout=15)
            if r.status_code == 200:
                d = r.json()
                return d.get("status"), d.get("transaction_amount", 0)
            return "error", 0
        except Exception as e:
            log(nome_bot, "ERRO", f"Exceção verificar PIX: {e}")
            return "error", 0

    async def liberar_acesso(uid, val, user_obj, q_msg, ctx):
        val = round(val, 2)
        plano = planos_usar.get(val)
        if not plano:
            log(nome_bot, "ERRO", f"❌ PLANO NÃO EXISTE — Valor R$ {val:.2f}")
            await q_msg.reply_text("❌ Esse plano não existe mais.")
            return
        seg, nome, grupo_id, grupo_link = plano
        uid = str(uid)
        
        tempo_expira = time.time() + seg if seg < 3153600000 else 3153600000
        username = f"@{user_obj.username}" if user_obj.username else "Sem @"
        data_compra = time.time()
        
        clientes_atual = carregar_clientes()
        clientes_atual[uid] = {
            "_id": uid,
            "nome": user_obj.first_name or "Cliente", 
            "username": username, 
            "expira_em": tempo_expira,
            "duracao_segundos": seg,
            "grupo": grupo_id, 
            "grupo_link": grupo_link, 
            "valor_pago": f"{val:.2f}",
            "data_compra": data_compra
        }
        salvar_clientes(clientes_atual)
        log(nome_bot, "VENDA", f"✅ LIBERADO — User:{uid} Valor:R${val} Plano:{nome}")

        data_compra_rj = formatar_data_rj(data_compra)
        data_expira_rj = "♾️ VITALÍCIO" if seg >= 3153600000 else formatar_data_rj(tempo_expira)

        if uid in msgs_para_apagar:
            try: await q_msg.delete_message()
            except: pass
            del msgs_para_apagar[uid]

        await q_msg.reply_text(
            f"✅ PAGAMENTO CONFIRMADO! 🎉\n\n🔗 Entre no grupo:\n👉 {grupo_link}\n\n📅 Compra: {data_compra_rj}\n⏳ Acesso: {data_expira_rj}"
        )

        try:
            await ctx.bot.send_message(dono_id,
                f"🆕 NOVA VENDA!\n👤 Cliente: {user_obj.first_name or 'Sem nome'}\n📱 Usuario: @{user_obj.username if user_obj.username else 'Sem @'}\n🆔 ID: {uid}\n💰 Valor: R$ {val:.2f}\n👥 Grupo: {grupo_link}\n📅 Data: {data_compra_rj}\n⏳ Acesso: {data_expira_rj}")
        except Exception as e:
            log(nome_bot, "ERRO", f"Não notificou dono: {e}")

    async def botoes(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
        q = update.callback_query
        d = q.data
        uid = str(update.effective_user.id)
        user = update.effective_user

        if esta_bloqueado(uid):
            if not aviso_ja_enviado(uid):
                await q.message.reply_text(MENSAGEM_BLOQUEADO)
            await q.answer()
            raise ApplicationHandlerStop

        if d.startswith("comprar_"):
            v = float(d.split("_")[1])
            
            try:
                await q.message.delete()
            except:
                pass

            ok, pid, qr = await gerar_pag(v, user)
            if ok:
                kb = [
                    [InlineKeyboardButton("📋 Copiar Código", copy_text=CopyTextButton(qr))],
                    [InlineKeyboardButton("✅ Verificar Pagamento", callback_data=f"check_{pid}_{v}")],
                    [InlineKeyboardButton("⬅️ Voltar", callback_data="voltar")]
                ]
                msg = await q.message.reply_text(
                    f"✅ PIX GERADO!\n\n💰 Valor: R$ {v:.2f}\n📋 Código Pix:\n{qr}\n\n⏰ Pague em até 10 minutos!",
                    reply_markup=InlineKeyboardMarkup(kb)
                )
                msgs_para_apagar[uid] = msg.message_id
                log(nome_bot, "USUARIO", f"PIX gerado — User:{uid} Valor:R${v} PID:{pid}")
            else:
                await q.message.reply_text(f"❌ {qr}")
            return

        elif d.startswith("check_"):
            partes = d.split("_")
            pid = partes[1]
            valor_esperado = float(partes[2]) if len(partes) > 2 else 0
            
            status, val_pago = await verif_pag(pid)
            
            if status == "approved":
                if abs(val_pago - valor_esperado) > 0.01:
                    await q.answer("⚠️ VALOR ERRADO!", show_alert=True)
                    await q.message.reply_text(
                        f"❌ PAGAMENTO COM VALOR DIFERENTE!\n\n"
                        f"Você pagou: R$ {val_pago:.2f}\n"
                        f"Valor do plano: R$ {valor_esperado:.2f}\n\n"
                        f"Pague o valor EXATO ou fale com o suporte."
                    )
                    return

                await q.answer("✅ PAGAMENTO APROVADO!", show_alert=True)
                await liberar_acesso(uid, valor_esperado, user, q.message, ctx)

            elif status == "pending":
                await q.answer("⏳ PENDENTE", show_alert=True)
                await q.message.reply_text("⏳ Ainda não identificado. Clique novamente em instantes.")
            else:
                await q.answer("❌ NÃO APROVADO", show_alert=True)
                await q.message.reply_text(f"❌ Status: {status}")
            return

        elif d == "voltar":
            if uid in msgs_para_apagar:
                try:
                    await ctx.bot.delete_message(chat_id=q.message.chat_id, message_id=msgs_para_apagar[uid])
                except:
                    try:
                        await q.message.delete()
                    except:
                        pass
                del msgs_para_apagar[uid]
            else:
                try:
                    await q.message.delete()
                except:
                    pass

            kb = []
            for valor, (seg, nome_plano, grupo_id, grupo_link) in planos_usar.items():
                kb.append([InlineKeyboardButton(f"{nome_plano} -> R$ {valor:.2f}", callback_data=f"comprar_{valor}")])
            kb.append([InlineKeyboardButton("📌 𝑷𝑹𝑬𝑽𝑰𝑨𝑺 𝑮𝑹𝑨𝑻𝑰𝑺 🔥", url="https://t.me/+zL_k2splzuZiYTUx")])
            mid = random.choice(lista_midias) if lista_midias else None
            await enviar_midia(ctx.bot, int(uid), mid, mensagem_inicial, InlineKeyboardMarkup(kb))
            return

    async def gerenciador_loop(app):
        if not is_principal: return
        while True:
            verificar_wifi()
            try:
                await expurgar_expirados(app.bot)
            except Exception as e:
                log(nome_bot, "ERRO", f"Erro no loop: {e}")
            gc.collect()
            await asyncio.sleep(300)

    verificar_wifi()

    try:
        app = ApplicationBuilder() \
            .token(token) \
            .connect_timeout(30.0) \
            .read_timeout(30.0) \
            .write_timeout(30.0) \
            .pool_timeout(20.0) \
            .build()

        app.add_handler(TypeHandler(Update, interceptar), group=-1)
        app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), log_mensagens), group=0)
        app.add_handler(CommandHandler("start", start))
        app.add_handler(CommandHandler("ping", ping_cmd))
        app.add_handler(CommandHandler("pin", pin_cmd))
        app.add_handler(CommandHandler("meu_id", meu_id_cmd))
        app.add_handler(CommandHandler("suporte", suporte_cmd))
        app.add_handler(CommandHandler("suport", suporte_cmd))
        app.add_handler(CommandHandler("pegarid", pegarid_cmd))
        app.add_handler(CommandHandler("clientes", clientes_cmd))
        app.add_handler(CommandHandler("clt", clientes_cmd))
        app.add_handler(CommandHandler("block", block_cmd))
        app.add_handler(CommandHandler("desbloquear", desbloquear_cmd))
        app.add_handler(CommandHandler("div", div_cmd))
        app.add_handler(CommandHandler("div2", div2_cmd))
        app.add_handler(CommandHandler("menu", menu_cmd))
        app.add_handler(CallbackQueryHandler(botoes))
        
        if is_principal and GRUPO_VIP is not None:
            app.add_handler(ChatMemberHandler(monitorar_entradas, ChatMemberHandler.CHAT_MEMBER))
            app.add_handler(ChatJoinRequestHandler(aprovar_solicitacao))

        log(nome_bot, "SISTEMA", "✅ BOT ONLINE!")
        await app.initialize()
        await app.start()
        
        if is_principal:
            try:
                await expurgar_expirados(app.bot)
            except Exception as e:
                log(nome_bot, "ERRO", f"Erro inicial: {e}")
            asyncio.create_task(gerenciador_loop(app))

        allowed = ["message", "callback_query", "chat_member", "my_chat_member", "chat_join_request"]
        await app.updater.start_polling(drop_pending_updates=False, allowed_updates=allowed)
        while True:
            verificar_wifi()
            await asyncio.sleep(60)
    except Exception as e:
        log(nome_bot, "ERRO", f"❌ FALHA: {e}")
        return

async def main():
    print("\n" + "="*60)
    print("LIGANDO...")
    print("="*60 + "\n")

    for idx, bot_cfg in enumerate(BOTS_CONFIG):
        if idx > 0:
            await asyncio.sleep(3)      
        eh_principal = (idx == 0)
        log("MAIN", "SISTEMA", f"🚀 INICIANDO {bot_cfg['nome']}...")
        asyncio.create_task(criar_e_iniciar_bot(bot_cfg, is_principal=eh_principal))
    while True:
        await asyncio.sleep(3600)

if __name__ == "__main__":
    while True:
        try:
            asyncio.run(main())
        except KeyboardInterrupt:
            print("\n⏹️ Encerrado")
            break
        except Exception as e:
            print(f"\n🔄 REINICIANDO... Erro: {e}")
            time.sleep(5)
