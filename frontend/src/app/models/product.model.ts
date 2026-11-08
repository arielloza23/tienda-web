export interface ProductVariant {
  id: number;
  sku: string;
  size?: string | null;
  color?: string | null;
  price_adjustment_cents: number;
}

export interface Product {
  id: number;
  name: string;
  slug: string;
  description?: string | null;
  price_cents: number;
  is_active: boolean;
  image_url?: string | null;
  variants: ProductVariant[];
}

export interface CartItem {
  product: Product;
  variant: ProductVariant | null;
  quantity: number;
}
