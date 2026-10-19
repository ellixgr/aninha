import os
from datetime import timezone, timedelta

FUSO_RJ = timezone(timedelta(hours=-3))

GRUPO_VIP = int(os.getenv("GRUPO_VIP", "-1004377588572"))
GRUPO_VIP_LINK = os.getenv("GRUPO_VIP_LINK", "https://t.me/+3flFzJUeyCA0M2Rh")

GRUPO_ANUAL_ID = int(os.getenv("GRUPO_ANUAL_ID", "-1004377588572"))
GRUPO_ANUAL_LINK = os.getenv("GRUPO_ANUAL_LINK", "https://t.me/+3flFzJUeyCA0M2Rh")

PLANOS_VIP_APENAS = {
    6.00:  (3600,     "⏳ 𝗩𝗜𝗣 𝗣𝗢𝗥 1 𝗛𝗢𝗥𝗔🔥",     GRUPO_VIP, GRUPO_VIP_LINK),
    11.00: (604800,   "📅 𝗩𝗜𝗣 𝗣𝗢𝗥 7 𝗗𝗜𝗔𝗦🔥🔥 (recomendado)",   GRUPO_VIP, GRUPO_VIP_LINK),
    29.90: (2592000,  "🗓️ 𝗩𝗜𝗣 𝗣𝗢𝗥 30 𝗗𝗜𝗔𝗦",      GRUPO_VIP, GRUPO_VIP_LINK),
    89.50: (31536000, "💎 𝗔𝗡𝗨𝗔𝗟 (𝗠𝗶𝗱𝗶𝗮𝘀 𝗿𝗮𝗿𝗮𝘀🤫𝗗𝗼𝘄𝗻𝗹𝗼𝗮𝗱𝘀 𝗹𝗶𝗯𝗲𝗿𝗮𝗱𝗼𝘀)", GRUPO_ANUAL_ID, GRUPO_ANUAL_LINK),
}
PLANOS_COMPLETOS = PLANOS_VIP_APENAS

MENSAGEM_VIP = """‼️⚠️*ACESSO TOTALMENTE ANÔNIMO(A)*⚠️‼️

🔐 _+100 MIL MÍDIAS LIBERADAS_
🔥 _Conteúdos que viralizam e somem da internet_
💀 _Mídias raras e difíceis de encontrar_
🕯️ _Atualização constante_
📥 _Downloads liberados_
💋 _Famosas / Privacy / OnlyFans_
🫦 _Exclusivos selecionados_

👇 💎*Escolha seu plano, você não vai se arrepender*🤭🔥:"""

# Pegando o token do Mercado Pago unificado para ambos os bots
MP_TOKEN_COMUM = os.getenv("MP_TOKEN", "")

BOTS_CONFIG = [
    {
        "nome": "aninha",
        "token": os.getenv("BOT_TOKEN_1", ""),
        "mp_token": MP_TOKEN_COMUM,
        "dono_id": int(os.getenv("DONO_ID", "7711945457")),
        "tipo_plano": "VIP",
        "midias": [
            "BAACAgEAAxkBAAINMWqHwstKPaNAoevtH_C8vbgx2rOiAAJ2BwAC2VFARLNksipNqGaVPQQ",
            "BAACAgEAAxkBAAINMmqHxQWRoW4M8dIocXIJgzoq6oDxAAJ6BwAC2VFARNbkIeRitsobPQQ",
            "BAACAgEAAxkBAAIUDGrSz4pByMyV8sm_i0CJKnA5CkK1AAJyDAACzV2ZRkBg1G5t867OPQQ",
            "BAACAgEAAxkBAAINNWqHxVapytBukUr0UbHZoVMnMtCzAALcBwACzV1ARIc0KzsoKhW8PQQ",
            "BAACAgEAAxkBAAIUD2rSz8xZKBNu8cUentRF-YsUssLKAAJ1DAACzV2ZRtezbZ__AivpPQQ",
            "BAACAgEAAxkBAAINamqHy2e_9QW8g064XL7HT671TR65AALvBwACzV1ARP2qWDrr3XeMPQQ",
            "BAACAgEAAxkBAAINN2qHxV1kw7CeT84jo3U7enhsXlJsAALdBwACzV1ARGiyDRO-vaSuPQQ",
            "BAACAgEAAxkBAAINM2qHxRhPrYP4wdJ6puHPGvfyc6LlAALbBwACzV1ARPSF-QtVJV2KPQQ",
            "BAACAgEAAxkBAAITtmrQ68aRSdvkX5WtIrETIc2-YrzrAALzCQACXTaJRqgDXHnOvjdzPQQ",
            "BAACAgEAAxkBAAIT62rSsiXwo8GvKgZKKNcSdhr6tRD2AALJCAACzV2RRsZGE79YbpNQPQQ",
            "BAACAgEAAxkBAAINNGqHxSYxz1SW7HILTo4B5aDSKTG3AAJ4BwAC2VFARDdsbR7JH0ouPQQ"
        ]
    },
    {
        "nome": "xay",
        "token": os.getenv("BOT_TOKEN_2", ""),
        "mp_token": MP_TOKEN_COMUM,
        "dono_id": int(os.getenv("DONO_ID", "7711945457")),
        "tipo_plano": "VIP",
        "midias": [
            "BAACAgEAAxkBAAIBf2qHvh2A0w5UFXjXg9vd2xF_eLOsAAJ2BwAC2VFARDvn3nM8HjNGPQQ",
            "BAACAgEAAxkBAAIBgmqHviyF2CvcncX5wXtqlwABBfJfOgACdwcAAtlRQEQLGGpSxnBPoz0E",
            "BAACAgEAAxkBAAIHJ2rQ7ARwYC81Om5g3zaOycYlPHEOAALzCQACXTaJRo1YsQABqhWLPj0E",
            "BAACAgEAAxkBAAIHTWrS0AFRpf00vo4w-gMF-oUTWmr4AAJyDAACzV2ZRubJqV-8F7FrPQQ",
            "BAACAgEAAxkBAAIHTmrS0AHF6FSKjFm6WDdTMDEBBNLWAAJ1DAACzV2ZRlXfbFi56qDVPQQ",
            "BAACAgEAAxkBAAIBhWqHvkvf21dcbMJhpFyVhpyzW5wUAAJ4BwAC2VFARCEHXfNOYOsvPQQ",
            "BAACAgEAAxkBAAIBiGqHvmtYYPvoaGrMiTYbJJ0vNNsfAAJ6BwAC2VFARGpx61vQSwGpPQQ"
        ]
    }
]
