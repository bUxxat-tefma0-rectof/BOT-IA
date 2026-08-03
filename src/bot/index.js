const TelegramBot = require('node-telegram-bot-api');
const { getDatabase } = require('../database/connection');
const IAService = require('../services/ia');
const pagamentoService = require('../services/pagamento');
const logger = require('../utils/helpers');

let bot = null;
const estados = new Map();

async function startBot() {
    bot = new TelegramBot(process.env.BOT_TOKEN, { polling: { interval: 300, autoStart: true } });
    
    // Comando /start
    bot.onText(/\/start/, async (msg) => {
        const chatId = msg.chat.id;
        const userId = msg.from.id;
        
        const db = getDatabase();
        let user = db.prepare('SELECT * FROM usuarios WHERE telegram_id = ?').get(userId);
        
        if (!user) {
            db.prepare('INSERT INTO usuarios (telegram_id, username, nome, creditos) VALUES (?, ?, ?, ?)').run(
                userId, msg.from.username, msg.from.first_name, parseInt(process.env.CREDITOS_INICIAIS || 5)
            );
            user = db.prepare('SELECT * FROM usuarios WHERE telegram_id = ?').get(userId);
        }
        
        await bot.sendMessage(chatId,
            `🤖 *Bem-vindo ao Bot IA!*\n\n` +
            `👋 Olá, *${msg.from.first_name}*!\n\n` +
            `🎯 Seus créditos: *${user.creditos}*\n\n` +
            `📋 *Comandos:*\n` +
            `💬 /ia - Conversar com IA\n` +
            `🎨 /imagem - Gerar imagem\n` +
            `🎬 /video - Gerar vídeo\n` +
            `💰 /creditos - Comprar créditos\n` +
            `👤 /perfil - Seu perfil\n\n` +
            `_Digite qualquer coisa para conversar!_`,
            { parse_mode: 'Markdown' }
        );
    });
    
    // Comando /ia - Conversar
    bot.onText(/\/ia/, (msg) => {
        estados.set(msg.from.id, { modo: 'texto' });
        bot.sendMessage(msg.chat.id, '💬 *Modo conversa ativado!*\n\nMe diga o que você quer saber ou perguntar:', { parse_mode: 'Markdown' });
    });
    
    // Comando /imagem - Gerar imagem
    bot.onText(/\/imagem/, (msg) => {
        estados.set(msg.from.id, { modo: 'imagem' });
        bot.sendMessage(msg.chat.id, '🎨 *Modo imagem ativado!*\n\nDescreva a imagem que você quer criar:\n\nEx: "Um gato astronauta no espaço, estilo realista"', { parse_mode: 'Markdown' });
    });
    
    // Comando /video - Gerar vídeo
    bot.onText(/\/video/, (msg) => {
        estados.set(msg.from.id, { modo: 'video' });
        bot.sendMessage(msg.chat.id, '🎬 *Modo vídeo ativado!*\n\nDescreva o vídeo que você quer criar:', { parse_mode: 'Markdown' });
    });
    
    // Comando /creditos - Comprar créditos
    bot.onText(/\/creditos/, async (msg) => {
        const db = getDatabase();
        const user = db.prepare('SELECT * FROM usuarios WHERE telegram_id = ?').get(msg.from.id);
        const planos = db.prepare('SELECT * FROM planos WHERE ativo = 1').all();
        
        let mensagem = `💰 *COMPRAR CRÉDITOS*\n\nSeus créditos: *${user.creditos}*\n\n*Planos:*\n`;
        const kb = { inline_keyboard: [] };
        
        for (const plano of planos) {
            mensagem += `📦 ${plano.nome}: *${plano.creditos} créditos* - R$ ${plano.valor.toFixed(2)}\n`;
            kb.inline_keyboard.push([
                { text: `💳 ${plano.nome} - R$ ${plano.valor.toFixed(2)}`, callback_data: `comprar_${plano.id}` }
            ]);
        }
        
        kb.inline_keyboard.push([{ text: '⬅️ Voltar', callback_data: 'menu_voltar' }]);
        
        await bot.sendMessage(msg.chat.id, mensagem, { parse_mode: 'Markdown', reply_markup: kb });
    });
    
    // Comando /perfil
    bot.onText(/\/perfil/, async (msg) => {
        const db = getDatabase();
        const user = db.prepare('SELECT * FROM usuarios WHERE telegram_id = ?').get(msg.from.id);
        
        await bot.sendMessage(msg.chat.id,
            `👤 *SEU PERFIL*\n\n` +
            `🆔 ID: \`${user.telegram_id}\`\n` +
            `📝 Nome: ${user.nome || 'N/A'}\n` +
            `🎯 Créditos: *${user.creditos}*\n` +
            `📊 Total gerado: *${user.total_gerado}*\n` +
            `📅 Desde: ${user.data_cadastro}`,
            { parse_mode: 'Markdown' }
        );
    });
    
    // Callback queries (botões)
    bot.on('callback_query', async (query) => {
        const chatId = query.message.chat.id;
        const userId = query.from.id;
        const data = query.data;
        
        bot.answerCallbackQuery(query.id);
        
        if (data === 'menu_voltar') {
            return bot.sendMessage(chatId, 'Volte ao menu com /start');
        }
        
        if (data.startsWith('comprar_')) {
            const planoId = data.split('_')[1];
            const db = getDatabase();
            const plano = db.prepare('SELECT * FROM planos WHERE id = ?').get(planoId);
            const user = db.prepare('SELECT * FROM usuarios WHERE telegram_id = ?').get(userId);
            
            if (!plano) return;
            
            await bot.sendMessage(chatId, `💳 Gerando PIX de R$ ${plano.valor.toFixed(2)}...`);
            
            const resultado = await pagamentoService.gerarPix(plano.valor, `Créditos Bot IA - ${plano.nome}`, user.id);
            
            if (!resultado.sucesso) {
                return bot.sendMessage(chatId, '❌ Erro ao gerar pagamento. Tente novamente.');
            }
            
            // Salva recarga
            db.prepare('INSERT INTO recargas (usuario_id, valor, creditos, payment_id) VALUES (?, ?, ?, ?)').run(
                user.id, plano.valor, plano.creditos, resultado.payment_id
            );
            
            // Envia QR Code
            await bot.sendPhoto(chatId, resultado.qrBuffer, {
                caption: `💳 *PAGAMENTO PIX*\n\n` +
                         `📦 ${plano.nome}: *${plano.creditos} créditos*\n` +
                         `💰 Valor: R$ ${plano.valor.toFixed(2)}\n\n` +
                         `📋 *PIX Copia e Cola:*\n\`${resultado.copia_cola}\`\n\n` +
                         `⏰ Expira em 30 minutos`,
                parse_mode: 'Markdown'
            });
            
            // Verifica pagamento automaticamente
            verificarPagamento(chatId, userId, resultado.payment_id, plano.creditos, 0);
        }
    });
    
    // Mensagens de texto
    bot.on('message', async (msg) => {
        if (msg.text && msg.text.startsWith('/')) return;
        if (!msg.text) return;
        
        const chatId = msg.chat.id;
        const userId = msg.from.id;
        const estado = estados.get(userId);
        const texto = msg.text;
        
        const db = getDatabase();
        const user = db.prepare('SELECT * FROM usuarios WHERE telegram_id = ?').get(userId);
        
        if (!user) return;
        
        // Se não tem modo definido, trata como conversa normal
        if (!estado || !estado.modo) {
            estados.set(userId, { modo: 'texto' });
        }
        
        const modo = estados.get(userId)?.modo || 'texto';
        
        // Verifica créditos
        const custos = {
            'texto': parseInt(process.env.CUSTO_TEXTO || 1),
            'imagem': parseInt(process.env.CUSTO_IMAGEM || 3),
            'video': parseInt(process.env.CUSTO_VIDEO || 10)
        };
        
        if (user.creditos < custos[modo]) {
            return bot.sendMessage(chatId,
                `❌ *Créditos insuficientes!*\n\n` +
                `Seus créditos: *${user.creditos}*\n` +
                `Necessário: *${custos[modo]}*\n\n` +
                `Use /creditos para comprar mais!`,
                { parse_mode: 'Markdown' }
            );
        }
        
        try {
            await bot.sendMessage(chatId, '⏳ Processando...');
            
            if (modo === 'texto') {
                const resposta = await IAService.gerarTexto(texto);
                db.prepare('UPDATE usuarios SET creditos = creditos - ?, total_gerado = total_gerado + 1 WHERE telegram_id = ?').run(custos.texto, userId);
                db.prepare('INSERT INTO historico (usuario_id, tipo, prompt, resultado, creditos_usados) VALUES (?,?,?,?,?)').run(user.id, 'texto', texto, resposta, custos.texto);
                await bot.sendMessage(chatId, resposta, { parse_mode: 'Markdown' });
            }
            
            else if (modo === 'imagem') {
                const resultado = await IAService.gerarImagem(texto);
                db.prepare('UPDATE usuarios SET creditos = creditos - ?, total_gerado = total_gerado + 1 WHERE telegram_id = ?').run(custos.imagem, userId);
                db.prepare('INSERT INTO historico (usuario_id, tipo, prompt, resultado, creditos_usados) VALUES (?,?,?,?,?)').run(user.id, 'imagem', texto, resultado.url, custos.imagem);
                await bot.sendPhoto(chatId, resultado.url, { caption: `🎨 *Imagem gerada!*\n\n📝 "${texto}"\n\nCréditos usados: ${custos.imagem}`, parse_mode: 'Markdown' });
            }
            
            else if (modo === 'video') {
                const resultado = await IAService.gerarVideo(texto);
                db.prepare('UPDATE usuarios SET creditos = creditos - ?, total_gerado = total_gerado + 1 WHERE telegram_id = ?').run(custos.video, userId);
                db.prepare('INSERT INTO historico (usuario_id, tipo, prompt, resultado, creditos_usados) VALUES (?,?,?,?,?)').run(user.id, 'video', texto, resultado.url, custos.video);
                await bot.sendPhoto(chatId, resultado.url, { caption: `🎬 *Vídeo gerado!*\n\n📝 "${texto}"\n\nCréditos usados: ${custos.video}`, parse_mode: 'Markdown' });
            }
        } catch (error) {
            await bot.sendMessage(chatId, `❌ ${error.message}`);
        }
    });
    
    logger.info('🤖 Bot principal configurado');
    return bot;
}

async function verificarPagamento(chatId, userId, paymentId, creditos, tentativas) {
    if (tentativas >= 30) return;
    
    setTimeout(async () => {
        const resultado = await pagamentoService.verificarPagamento(paymentId);
        
        if (resultado.aprovado) {
            const db = getDatabase();
            db.prepare('UPDATE usuarios SET creditos = creditos + ? WHERE telegram_id = ?').run(creditos, userId);
            db.prepare('UPDATE recargas SET status = ? WHERE payment_id = ?').run('aprovado', paymentId);
            
            const user = db.prepare('SELECT creditos FROM usuarios WHERE telegram_id = ?').get(userId);
            await bot.sendMessage(chatId, `✅ *Pagamento aprovado!*\n\n🎯 Novos créditos: *${user.creditos}*\n(+${creditos} créditos)`, { parse_mode: 'Markdown' });
        } else {
            verificarPagamento(chatId, userId, paymentId, creditos, tentativas + 1);
        }
    }, 10000);
}

function getBot() { return bot; }

module.exports = { startBot, getBot };
