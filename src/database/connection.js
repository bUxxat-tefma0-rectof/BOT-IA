const Database = require('better-sqlite3');
const path = require('path');
const fs = require('fs');

let db = null;

function getDatabase() {
    if (!db) {
        const dbPath = process.env.DATABASE_PATH || './botia.db';
        const dir = path.dirname(dbPath);
        if (!fs.existsSync(dir)) fs.mkdirSync(dir, { recursive: true });
        
        db = new Database(dbPath);
        db.pragma('journal_mode = WAL');
        db.pragma('foreign_keys = ON');
    }
    return db;
}

async function initDatabase() {
    const db = getDatabase();
    
    db.exec(`
        CREATE TABLE IF NOT EXISTS usuarios (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            telegram_id BIGINT UNIQUE NOT NULL,
            username TEXT,
            nome TEXT,
            creditos INTEGER DEFAULT ${process.env.CREDITOS_INICIAIS || 5},
            total_gerado INTEGER DEFAULT 0,
            bloqueado INTEGER DEFAULT 0,
            data_cadastro DATETIME DEFAULT CURRENT_TIMESTAMP
        );
        
        CREATE TABLE IF NOT EXISTS historico (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            usuario_id INTEGER,
            tipo TEXT NOT NULL,
            prompt TEXT,
            resultado TEXT,
            creditos_usados INTEGER,
            data DATETIME DEFAULT CURRENT_TIMESTAMP
        );
        
        CREATE TABLE IF NOT EXISTS recargas (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            usuario_id INTEGER,
            valor REAL,
            creditos INTEGER,
            payment_id TEXT,
            status TEXT DEFAULT 'pendente',
            data DATETIME DEFAULT CURRENT_TIMESTAMP
        );
        
        CREATE TABLE IF NOT EXISTS planos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nome TEXT NOT NULL,
            valor REAL NOT NULL,
            creditos INTEGER NOT NULL,
            ativo INTEGER DEFAULT 1
        );
        
        CREATE TABLE IF NOT EXISTS config (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            chave TEXT UNIQUE NOT NULL,
            valor TEXT
        );
    `);
    
    // Insere planos padrão
    const planos = db.prepare('SELECT COUNT(*) as t FROM planos').get();
    if (planos.t === 0) {
        db.prepare('INSERT INTO planos (nome, valor, creditos) VALUES (?,?,?)').run('Básico', 10, 50);
        db.prepare('INSERT INTO planos (nome, valor, creditos) VALUES (?,?,?)').run('Plus', 20, 120);
        db.prepare('INSERT INTO planos (nome, valor, creditos) VALUES (?,?,?)').run('Premium', 50, 350);
    }
}

module.exports = { getDatabase, initDatabase };
