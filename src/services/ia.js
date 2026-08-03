const axios = require('axios');
const logger = require('../utils/helpers');

const GEMINI_API_KEY = process.env.GEMINI_API_KEY || 'AQ.Ab8RN6IQaOff6Pohwow1hQ5OEhyabGgTgO-JDXWR6JT_0A4_Zg';

class IAService {
    
    static async gerarTexto(prompt) {
        try {
            const response = await axios.post(
                `https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash-exp:generateContent?key=${GEMINI_API_KEY}`,
                {
                    contents: [{
                        parts: [{
                            text: `Busque informações atualizadas na internet e responda em português do Brasil: ${prompt}`
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
            if (response.data.candidates[0].groundingMetadata) {
                const sources = response.data.candidates[0].groundingMetadata.groundingChunks || [];
                if (sources.length > 0) {
                    links = '\n\n🔗 *Fontes:*\n';
                    sources.slice(0, 3).forEach((s, i) => {
                        if (s.web) {
                            links += `   ${i+1}. ${s.web.title || 'Link'}: ${s.web.uri}\n`;
                        }
                    });
                }
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
                    { role: 'system', content: 'Responda em português do Brasil de forma útil.' },
                    { role: 'user', content: prompt }
                ],
                max_tokens: 2000
            });
            
            return response.choices[0].message.content + '\n\n⚠️ _Resposta sem busca na web (Gemini indisponível)_';
            
        } catch (err) {
            throw new Error('Todos os serviços de IA estão indisponíveis. Tente novamente.');
        }
    }
    
    static async gerarImagem(prompt) {
        try {
            const imageUrl = `https://image.pollinations.ai/prompt/${encodeURIComponent(prompt)}?width=1024&height=1024&nologo=true`;
            return { url: imageUrl, revised_prompt: prompt };
        } catch (error) {
            throw new Error('Erro ao gerar imagem.');
        }
    }
    
    static async gerarVideo(prompt) {
        try {
            const imageUrl = `https://image.pollinations.ai/prompt/${encodeURIComponent(prompt + ', cinematic, motion')}?width=1024&height=1024&nologo=true`;
            return { url: imageUrl, mensagem: '🎬 Vídeo conceitual gerado!', revised_prompt: prompt };
        } catch (error) {
            throw new Error('Erro ao gerar vídeo.');
        }
    }
}

module.exports = IAService;
