const { MercadoPagoConfig, Payment } = require('mercadopago');
const QRCode = require('qrcode');
const logger = require('../utils/helpers');

class PagamentoService {
    
    constructor() {
        this.client = new MercadoPagoConfig({
            accessToken: process.env.MERCADO_PAGO_ACCESS_TOKEN
        });
    }
    
    async gerarPix(valor, descricao, usuarioId) {
        try {
            const payment = new Payment(this.client);
            
            const body = {
                transaction_amount: Number(valor),
                description: descricao,
                payment_method_id: 'pix',
                payer: {
                    email: `user${usuarioId}@botia.com`
                }
            };
            
            const response = await payment.create({ body });
            
            const pix = {
                qr_code_base64: response.point_of_interaction.transaction_data.qr_code_base64,
                copia_cola: response.point_of_interaction.transaction_data.qr_code,
                payment_id: response.id,
                status: response.status
            };
            
            // Gera QR Code como buffer
            const qrBuffer = await QRCode.toBuffer(pix.copia_cola);
            
            return { sucesso: true, ...pix, qrBuffer };
            
        } catch (error) {
            logger.error('Erro PIX: ' + error.message);
            return { sucesso: false, mensagem: 'Erro ao gerar pagamento' };
        }
    }
    
    async verificarPagamento(paymentId) {
        try {
            const payment = new Payment(this.client);
            const response = await payment.get({ id: paymentId });
            
            return {
                status: response.status,
                aprovado: response.status === 'approved'
            };
        } catch (error) {
            return { status: 'error', aprovado: false };
        }
    }
}

module.exports = new PagamentoService();
