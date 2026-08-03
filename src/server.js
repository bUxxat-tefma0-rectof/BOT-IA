require('dotenv').config();
const express = require('express');
const path = require('path');
const { initDatabase, getDatabase } = require('./database/connection');
const { startBot } = require('./bot/index');
const { startAdminBot } = require('./bot/admin');
const logger = require('./utils/helpers');

const app = express();
const PORT = process.env.PORT || 3000;

process.on('unhandledRejection', (error) => {
    logger.error('Erro: ' + (error?.message || 'Erro desconhecido'));
});

app.use(express.json());
app.use(express.static(path.join(__dirname, '..', 'public')));

// ============ ROTAS WEB ============

// Página inicial
app.get('/', (req, res) => {
    res.json({ 
        status: 'online', 
        bot: '🤖 Bot IA Telegram',
        funcionalidades: ['Conversa IA', 'Gerar Imagens', 'Gerar Vídeos', 'Créditos', 'Pagamento PIX'],
        timestamp: new Date().toISOString()
    });
});

// Painel admin web
app.get('/admin', (req, res) => {
    res.sendFile(path.join(__dirname, '..', 'public', 'admin.html'));
});

// ============ API ADMIN ============

// Estatísticas do painel
app.get('/api/admin/stats', (req, res) => {
    try {
        const db = getDatabase();
        const totalUsers = db.prepare('SELECT COUNT(*) as t FROM usuarios').get().t;
        const faturamento = db.prepare("SELECT COALESCE(SUM(valor),0) as t FROM recargas WHERE status='aprovado'").get().t;
        const totalGerado = db.prepare('SELECT COUNT(*) as t FROM historico').get().t;
        const recargasHoje = db.prepare("SELECT COUNT(*) as t FROM recargas WHERE date(data)=date('now') AND status='aprovado'").get().t;
        const usersAtivos = db.prepare('SELECT COUNT(*) as t FROM usuarios WHERE creditos > 0').get().t;
        
        res.json({ 
            totalUsers, 
            faturamento, 
            totalGerado, 
            recargasHoje,
            usersAtivos
        });
    } catch (error) {
        res.json({ error: error.message });
    }
});

// Adicionar créditos a um usuário
app.post('/api/admin/add-creditos', (req, res) => {
    try {
        const { userId, creditos } = req.body;
        
        if (!userId || !creditos || creditos <= 0) {
            return res.json({ sucesso: false, mensagem: 'Dados inválidos' });
        }
        
        const db = getDatabase();
        const user = db.prepare('SELECT * FROM usuarios WHERE telegram_id = ?').get(userId);
        
        if (!user) {
            return res.json({ sucesso: false, mensagem: 'Usuário não encontrado' });
        }
        
        db.prepare('UPDATE usuarios SET creditos = creditos + ? WHERE telegram_id = ?').run(creditos, userId);
        
        logger.info(`💰 Admin adicionou ${creditos} créditos para ${userId}`);
        
        res.json({ 
            sucesso: true, 
            mensagem: `${creditos} créditos adicionados para o usuário ${userId}`,
            creditosAtuais: user.creditos + creditos
        });
    } catch (error) {
        res.json({ sucesso: false, mensagem: error.message });
    }
});

// Remover créditos de um usuário
app.post('/api/admin/remove-creditos', (req, res) => {
    try {
        const { userId, creditos } = req.body;
        
        if (!userId || !creditos || creditos <= 0) {
            return res.json({ sucesso: false, mensagem: 'Dados inválidos' });
        }
        
        const db = getDatabase();
        const user = db.prepare('SELECT * FROM usuarios WHERE telegram_id = ?').get(userId);
        
        if (!user) {
            return res.json({ sucesso: false, mensagem: 'Usuário não encontrado' });
        }
        
        db.prepare('UPDATE usuarios SET creditos = MAX(0, creditos - ?) WHERE telegram_id = ?').run(creditos, userId);
        
        res.json({ sucesso: true, mensagem: `${creditos} créditos removidos do usuário ${userId}` });
    } catch (error) {
        res.json({ sucesso: false, mensagem: error.message });
    }
});

// Bloquear/desbloquear usuário
app.post('/api/admin/toggle-ban', (req, res) => {
    try {
        const { userId } = req.body;
        
        if (!userId) {
            return res.json({ sucesso: false, mensagem: 'ID do usuário é obrigatório' });
        }
        
        const db = getDatabase();
        const user = db.prepare('SELECT * FROM usuarios WHERE telegram_id = ?').get(userId);
        
        if (!user) {
            return res.json({ sucesso: false, mensagem: 'Usuário não encontrado' });
        }
        
        const novoStatus = user.bloqueado ? 0 : 1;
        db.prepare('UPDATE usuarios SET bloqueado = ? WHERE telegram_id = ?').run(novoStatus, userId);
        
        res.json({ 
            sucesso: true, 
            mensagem: `Usuário ${novoStatus ? 'bloqueado' : 'desbloqueado'} com sucesso`,
            bloqueado: novoStatus
        });
    } catch (error) {
        res.json({ sucesso: false, mensagem: error.message });
    }
});

// Listar todos os usuários
app.get('/api/admin/usuarios', (req, res) => {
    try {
        const db = getDatabase();
        const usuarios = db.prepare('SELECT * FROM usuarios ORDER BY creditos DESC LIMIT 100').all();
        res.json({ usuarios });
    } catch (error) {
        res.json({ error: error.message });
    }
});

// Listar últimas recargas
app.get('/api/admin/recargas', (req, res) => {
    try {
        const db = getDatabase();
        const recargas = db.prepare(`
            SELECT r.*, u.username, u.nome 
            FROM recargas r 
            LEFT JOIN usuarios u ON r.usuario_id = u.id 
            ORDER BY r.data DESC 
            LIMIT 50
        `).all();
        res.json({ recargas });
    } catch (error) {
        res.json({ error: error.message });
    }
});

// Histórico de geração
app.get('/api/admin/historico', (req, res) => {
    try {
        const db = getDatabase();
        const historico = db.prepare(`
            SELECT h.*, u.username, u.nome 
            FROM historico h 
            LEFT JOIN usuarios u ON h.usuario_id = u.id 
            ORDER BY h.data DESC 
            LIMIT 50
        `).all();
        res.json({ historico });
    } catch (error) {
        res.json({ error: error.message });
    }
});

// Broadcast (enviar mensagem para todos)
app.post('/api/admin/broadcast', async (req, res) => {
    try {
        const { mensagem } = req.body;
        
        if (!mensagem) {
            return res.json({ sucesso: false, mensagem: 'Mensagem é obrigatória' });
        }
        
        const db = getDatabase();
        const usuarios = db.prepare('SELECT telegram_id FROM usuarios WHERE bloqueado = 0').all();
        
        const bot = require('./bot/index').getBot();
        let enviados = 0;
        let falhas = 0;
        
        for (const user of usuarios) {
            try {
                await bot.sendMessage(user.telegram_id, `📢 *AVISO ADMIN*\n\n${mensagem}`, { parse_mode: 'Markdown' });
                enviados++;
            } catch (e) {
                falhas++;
            }
        }
        
        res.json({ 
            sucesso: true, 
            mensagem: `Mensagem enviada para ${enviados} usuários (${falhas} falhas)`,
            enviados,
            falhas
        });
    } catch (error) {
        res.json({ sucesso: false, mensagem: error.message });
    }
});

// ============ API PÚBLICA ============

// Verificar créditos de um usuário
app.get('/api/creditos/:userId', (req, res) => {
    try {
        const db = getDatabase();
        const user = db.prepare('SELECT creditos, nome FROM usuarios WHERE telegram_id = ?').get(req.params.userId);
        
        if (!user) {
            return res.json({ error: 'Usuário não encontrado' });
        }
        
        res.json({ creditos: user.creditos, nome: user.nome });
    } catch (error) {
        res.json({ error: error.message });
    }
});

// ============ INICIAR SISTEMA ============

async function main() {
    logger.info('🤖 Iniciando Bot IA...');
    
    await initDatabase();
    logger.info('✅ Banco de dados pronto');
    
    await startBot();
    logger.info('✅ Bot principal online');
    
    await startAdminBot();
    logger.info('✅ Bot admin online');
    
    app.listen(PORT, () => {
        logger.info(`🌐 Servidor web na porta ${PORT}`);
        logger.info(`📊 Painel admin: http://localhost:${PORT}/admin`);
        logger.info('🤖 Bot IA pronto para usar!');
    });
}

main().catch(error => {
    logger.error('Erro fatal: ' + (error?.message || 'Erro'));
    process.exit(1);
});
