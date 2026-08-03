const axios = require('axios');
const logger = require('../utils/helpers');

const GROQ_API_KEY = process.env.GROQ_API_KEY || 'gsk_SuaChaveGroqAqui';

class IAService {
    
    static async gerarTexto(prompt) {
        try {
            const response = await axios.post('https://api.groq.com/openai/v1/chat/completions', {
                model: 'llama-3.3-70b-versatile',
                messages: [
                    { role: 'system', content: 'Você é um assistente inteligente e criativo. Responda em português.' },
                    { role: 'user', content: prompt }
                ],
                max_tokens: 1000
            }, {
                headers: {
                    'Authorization': `Bearer ${GROQ_API_KEY}`,
                    'Content-Type': 'application/json'
                }
            });
            
            return response.data.choices[0].message.content;
        } catch (error) {
            logger.error('Erro IA: ' + (error.response?.data?.error?.message || error.message));
            throw new Error('Erro ao gerar texto.');
        }
    }
    
    static async gerarImagem(prompt) {
        // Groq não gera imagens, então usamos uma API gratuita alternativa
        try {
            const response = await axios.post('https://api.deepai.org/api/text2img', {
                text: prompt
            }, {
                headers: { 'api-key': 'quickstart-QUdJIGlzIGNvbWluZy4uLi4K' }
            });
            
            return {
                url: response.data.output_url,
                revised_prompt: prompt
            };
        } catch (error) {
            throw new Error('Erro ao gerar imagem. Use /creditos para comprar mais.');
        }
    }
    
    static async gerarVideo(prompt) {
        throw new Error('Geração de vídeo requer créditos. Use /creditos para comprar.');
    }
}

module.exports = IAService;
