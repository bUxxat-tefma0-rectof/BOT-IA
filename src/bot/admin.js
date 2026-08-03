const TelegramBot = require('node-telegram-bot-api');
const { getDatabase } = require('../database/connection');
const logger = require('../utils/helpers');

let adminBot = null;

async function startAdminBot() {
    adminBot = new TelegramBot(process.env.BOT_TOKEN, { polling: false });
    
    // Usa o mesmo bot, mas com comandos admin
    const clientBot = require('./index').getBot();
    
    clientBot.onText(/\/admin/, async (msg) => {
        const adminIds = process.env.ADMIN_IDS.split(',').map(Number);
        if (!adminIds.includes(msg.from.id)) return;
        
        const db = getDatabase();
        const totalUsers = db.prepare('SELECT COUNT(*) as t FROM usuarios').get().t;
        const totalRecargas = db.prepare("SELECT COALESCE(SUM(valor),0) as t FROM recargas WHERE status='aprovado'").get().t;
        const totalGerado = db.prepare('SELECT COUNT(*) as t FROM historico').get().t;
        
        await clientBot.sendMessage(msg.chat.id,
            `📊 *PAINEL ADMIN*\n\n` +
            `👥 Usuários: *${totalUsers}*\n` +
            `💰 Faturamento: R$ *${totalRecargas.toFixed(2)}*\n` +
            `🎯 Total gerado: *${totalGerado}*\n\n` +
            `⚙️ Comandos:\n` +
            `/creditos_add ID QUANTIDADE - Adicionar créditos\n` +
            `/creditos_remover ID QUANTIDADE - Remover créditos\n` +
            `/ban ID - Banir usuário\n` +
            `/unban ID - Desbanir\n` +
            `/broadcast TEXTO - Enviar para todos`,
            { parse_mode: 'Markdown' }
        );
    });
    
    // Adicionar créditos
    clientBot.onText(/\/creditos_add (\d+) (\d+)/, async (msg, match) => {
        const adminIds = process.env.ADMIN_IDS.split(',').map(Number);
        if (!adminIds.includes(msg.from.id)) return;
        
        const targetId = match[1];
        const qtd = parseInt(match[2]);
        
        const db = getDatabase();
        db.prepare('UPDATE usuarios SET creditos = creditos + ? WHERE telegram_id = ?').run(qtd, targetId);
        
        await clientBot.sendMessage(msg.chat.id, `✅ ${qtd} créditos adicionados para ${targetId}`);
    });
    
    // Broadcast
    clientBot.onText(/\/broadcast (.+)/, async (msg, match) => {
        const adminIds = process.env.ADMIN_IDS.split(',').map(Number);
        if (!adminIds.includes(msg.from.id)) return;
        
        const texto = match[1];
        const db = getDatabase();
        const users = db.prepare('SELECT telegram_id FROM usuarios WHERE bloqueado = 0').all();
        
        let enviados = 0;
        for (const user of users) {
            try {
                await clientBot.sendMessage(user.telegram_id, `📢 *AVISO*\n\n${texto}`, { parse_mode: 'Markdown' });
                enviados++;
            } catch (e) {}
        }
        
        await clientBot.sendMessage(msg.chat.id, `✅ Enviado para ${enviados} usuários`);
    });
    
    logger.info('👑 Admin configurado');
}

module.exports = { startAdminBot };
