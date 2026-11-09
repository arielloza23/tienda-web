export interface ProductVariant {
  id: number;
  sku: string;
  size?: string | null;
  color?: string | null;
  price_adjustment_cents: number;
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
  is_active: boolean;
  image_url?: string | null;
  images?: ProductImage[];
  variants: ProductVariant[];
}

export interface CartItem {
  product: Product;
  variant: ProductVariant | null;
  quantity: number;
}
