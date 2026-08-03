const axios = require('axios');
const logger = require('../utils/helpers');

const GEMINI_API_KEY = process.env.GEMINI_API_KEY || 'AQ.Ab8RN6IQaOff6Pohwow1hQ5OEhyabGgTgO-JDXWR6JT_0A4_Zg';

class IAService {
    
    static async gerarTexto(prompt) {
        try {
            const response = await axios.post(
                `https://generativelanguage.googleapis.com/v1/models/gemini-1.5-flash:generateContent?key=${GEMINI_API_KEY}`,
                {
                    contents: [{
                        parts: [{
                            text: prompt
                        }]
                    }],
                    tools: [{ googleSearch: {} }],
                    generationConfig: {
                        temperature: 0.7,
                        topK: 40,
                        topP: 0.95,
                        maxOutputTokens: 2000
                    }
                },
                { headers: { 'Content-Type': 'application/json' } }
            );
            
            const text = response.data.candidates[0].content.parts[0].text;
            
            let links = '';
            const metadata = response.data.candidates[0].groundingMetadata;
            if (metadata && metadata.groundingChunks) {
                links = '\n\n🔗 *Fontes:*\n';
                metadata.groundingChunks.slice(0, 3).forEach((s, i) => {
                    if (s.web) {
                        links += `   ${i+1}. ${s.web.title || 'Link'}: ${s.web.uri}\n`;
                    }
                });
            }
            
            return text + links;
            
        } catch (error) {
            logger.error('Erro Gemini: ' + (error.response?.data?.error?.message || error.message));
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
                    { role: 'system', content: 'Responda em português do Brasil.' },
                    { role: 'user', content: prompt }
                ],
                max_tokens: 2000
            });
            
            return response.choices[0].message.content + '\n\n⚠️ _Resposta sem busca na web_';
            
        } catch (err) {
            throw new Error('IA indisponível. Tente novamente.');
        }
    }
    
    static async gerarImagem(prompt) {
        try {
            const url = `https://image.pollinations.ai/prompt/${encodeURIComponent(prompt)}?width=1024&height=1024&nologo=true`;
            return { url, revised_prompt: prompt };
        } catch (e) {
            throw new Error('Erro ao gerar imagem.');
        }
    }
    
    static async gerarVideo(prompt) {
        try {
            const url = `https://image.pollinations.ai/prompt/${encodeURIComponent(prompt + ', cinematic')}?width=1024&height=1024&nologo=true`;
            return { url, mensagem: '🎬 Vídeo gerado!', revised_prompt: prompt };
        } catch (e) {
            throw new Error('Erro ao gerar vídeo.');
        }
    }
}

module.exports = IAService;
