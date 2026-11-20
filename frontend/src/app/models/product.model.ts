export interface ProductVariant {
  id: number;
  sku: string;
  size?: string | null;
  color?: string | null;
  price_adjustment_cents: number;
  stock_quantity?: number;
  /** Contornos de la prenda en centímetros; no son medidas corporales recomendadas. */
  bust_cm?: number | null;
  waist_cm?: number | null;
  hip_cm?: number | null;
}

export interface ProductImage {
  id: number;
  url: string;
  alt: string;
  color: string;
}

export interface Product {
  id: number;
  name: string;
  slug: string;
  description?: string | null;
  price_cents: number;
  stock_quantity?: number;
  is_active: boolean;
  image_url?: string | null;
  images?: ProductImage[];
  variants: ProductVariant[];
}

export function availableQuantity(product: Product, variant: ProductVariant | null = null): number {
  const stock = variant ? variant.stock_quantity : product.stock_quantity;
  return stock === undefined ? 100 : Math.max(0, Math.min(100, stock));
}

export interface CartItem {
  product: Product;
  variant: ProductVariant | null;
  quantity: number;
}
