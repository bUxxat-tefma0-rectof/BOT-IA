const axios = require('axios');
const logger = require('../utils/helpers');

const GEMINI_API_KEY = process.env.GEMINI_API_KEY || 'AQ.Ab8RN6IQaOff6Pohwow1hQ5OEhyabGgTgO-JDXWR6JT_0A4_Zg';

class IAService {
    
    static async gerarTexto(prompt) {
        try {
            // Tenta gemini-pro (mais compatível)
            const response = await axios.post(
                `https://generativelanguage.googleapis.com/v1/models/gemini-pro:generateContent?key=${GEMINI_API_KEY}`,
                {
                    contents: [{
                        parts: [{ text: prompt }]
                    }],
                    generationConfig: {
                        temperature: 0.7,
                        maxOutputTokens: 2000
                    }
                },
                { headers: { 'Content-Type': 'application/json' } }
            );
            
            const text = response.data.candidates[0].content.parts[0].text;
            return text;
            
        } catch (error) {
            logger.error('Erro Gemini: ' + (error.response?.data?.error?.message || error.message));
            // Se Gemini falhar, usa Groq direto
            return await this.fallbackGroq(prompt);
        }
    }
    
    static async fallbackGroq(prompt) {
        try {
            const OpenAI = require('openai');
            const groq = new OpenAI({
                apiKey: process.env.GROQ_API_KEY || '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',
                baseURL: 'https://api.groq.com/openai/v1'
            });
            
            const response = await groq.chat.completions.create({
                model: 'llama-3.3-70b-versatile',
                messages: [
                    { role: 'system', content: 'Você é um assistente inteligente. Responda em português do Brasil de forma completa e útil. Quando não souber algo, seja honesto.' },
                    { role: 'user', content: prompt }
                ],
                max_tokens: 2000,
                temperature: 0.7
            });
            
            return response.choices[0].message.content;
            
        } catch (err) {
            logger.error('Erro Groq: ' + err.message);
            throw new Error('IA temporariamente indisponível. Tente novamente em instantes.');
        }
    }
    
    static async gerarImagem(prompt) {
        try {
            const url = `https://image.pollinations.ai/prompt/${encodeURIComponent(prompt)}?width=1024&height=1024&nologo=true`;
            return { url, revised_prompt: prompt };
        } catch (e) {
            throw new Error('Erro ao gerar imagem. Tente novamente.');
        }
    }
    
    static async gerarVideo(prompt) {
        try {
            const url = `https://image.pollinations.ai/prompt/${encodeURIComponent(prompt + ', cinematic, motion')}?width=1024&height=1024&nologo=true`;
            return { url, mensagem: '🎬 Vídeo gerado!', revised_prompt: prompt };
        } catch (e) {
            throw new Error('Erro ao gerar vídeo. Tente novamente.');
        }
    }
}

module.exports = IAService;
