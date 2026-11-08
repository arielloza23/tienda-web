export interface OrderCreateRequest {
  customer_name: string;
  customer_phone: string;
  delivery_address: string;
  /** Opcionales; si se envía una, hay que enviar ambas. */
  delivery_latitude?: number;
  delivery_longitude?: number;
  items: Array<{
    product_id: number;
    variant_id?: number;
    quantity: number;
  }>;
}

export interface OrderReceipt {
  id: number;
  customer_name: string | null;
  customer_phone: string | null;
  delivery_address: string | null;
  delivery_latitude: number | null;
  delivery_longitude: number | null;
  status: string;
  subtotal_cents: number;
  total_cents: number;
  items: Array<{
    product_name: string;
    variant_label: string | null;
    quantity: number;
    total_price_cents: number;
  }>;
}