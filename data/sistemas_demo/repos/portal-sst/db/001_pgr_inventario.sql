-- Inventário de riscos do PGR (sistema fictício de demonstração)
CREATE TABLE pgr_inventario (
  id SERIAL PRIMARY KEY,
  unidade_id INTEGER NOT NULL,
  categoria VARCHAR(20) NOT NULL,
  descricao TEXT NOT NULL,
  nivel_risco VARCHAR(10) NOT NULL,
  revisado_em DATE
);
