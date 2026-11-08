// Categorias do inventário de riscos do PGR (sistema fictício de demonstração)
export const CATEGORIAS_RISCO = ['físico', 'químico', 'biológico', 'ergonômico', 'acidente'];

export function categoriaValida(c: string): boolean {
  return CATEGORIAS_RISCO.includes(c);
}
