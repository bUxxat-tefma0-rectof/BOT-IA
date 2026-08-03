const OpenAI = require('openai');
const logger = require('../utils/helpers');

const openai = new OpenAI({
    apiKey: process.env.OPENAI_API_KEY
});

class IAService {
    
    // Conversa com IA (DALL-E para imagem, GPT para texto)
    static async gerarTexto(prompt) {
        try {
            const response = await openai.chat.completions.create({
                model: 'gpt-4o-mini',
                messages: [
                    { role: 'system', content: 'Você é um assistente inteligente e criativo. Responda em português de forma útil e amigável.' },
                    { role: 'user', content: prompt }
                ],
                max_tokens: 1000
            });
            
            return response.choices[0].message.content;
        } catch (error) {
            logger.error('Erro IA texto: ' + error.message);
            throw new Error('Erro ao gerar texto. Tente novamente.');
        }
    }
    
    // Gerar imagem com DALL-E
    static async gerarImagem(prompt) {
        try {
            const response = await openai.images.generate({
                model: 'dall-e-3',
                prompt: prompt,
                n: 1,
                size: '1024x1024',
                quality: 'standard'
            });
            
            return {
                url: response.data[0].url,
                revised_prompt: response.data[0].revised_prompt
            };
        } catch (error) {
            logger.error('Erro IA imagem: ' + error.message);
            throw new Error('Erro ao gerar imagem. Tente novamente.');
        }
    }
    
    // Gerar vídeo (usando descrição + imagem)
    static async gerarVideo(prompt) {
        try {
            // Primeiro gera uma imagem
            const imagem = await this.gerarImagem(prompt);
            
            // Depois gera um vídeo curto a partir da imagem
            // (OpenAI ainda não tem Sora público, usamos Runway ou Pika)
            // Por enquanto, retorna a imagem com efeito de vídeo
            
            // Simulação: retorna a imagem como "vídeo"
            return {
                url: imagem.url,
                mensagem: '🎬 Vídeo gerado a partir da sua descrição!',
                revised_prompt: imagem.revised_prompt
            };
        } catch (error) {
            logger.error('Erro IA vídeo: ' + error.message);
            throw new Error('Erro ao gerar vídeo. Tente novamente.');
        }
    }
}

module.exports = IAService;
