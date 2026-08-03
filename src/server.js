require('dotenv').config();
const express = require('express');
const path = require('path');
const { initDatabase } = require('./database/connection');
const { startBot } = require('./bot/index');
const { startAdminBot } = require('./bot/admin');
const logger = require('./utils/helpers');

const app = express();
const PORT = process.env.PORT || 3000;

app.use(express.json());
app.use(express.static(path.join(__dirname, '..', 'public')));

app.get('/', (req, res) => {
    res.json({ status: 'online', bot: '🤖 Bot IA Telegram' });
});

async function main() {
    logger.info('🤖 Iniciando Bot IA...');
    await initDatabase();
    logger.info('✅ Banco pronto');
    
    await startBot();
    logger.info('✅ Bot principal online');
    
    await startAdminBot();
    logger.info('✅ Bot admin online');
    
    app.listen(PORT, () => {
        logger.info(`🌐 Porta ${PORT}`);
        logger.info('🤖 Bot IA pronto!');
    });
}

main().catch(err => {
    logger.error('Erro: ' + err.message);
    process.exit(1);
});
