import { Product } from '../models/product.model';
import { ProductCreate, ProductUpdate } from './admin-api.service';

export interface ProductDraft {
  name: string; slug: string; description: string; price: string; is_active: boolean; coverUrl: string;
  variants: Array<{ id?: number; sku: string; size: string; color: string; adjustment: string; bust_cm?: string; waist_cm?: string; hip_cm?: string }>;
  images: Array<{ url: string; alt: string; color: string }>;
}
export function emptyProductDraft(): ProductDraft {
  return { name: '', slug: '', description: '', price: '', is_active: true, coverUrl: '', variants: [], images: [] };
}
export function priceToCents(value: string): number {
  const normalized = value.trim().replace(',', '.');
  if (!/^\d+(?:\.\d{1,2})?$/.test(normalized)) throw new Error('Escribe un importe válido con un máximo de dos decimales.');
  const [whole, fraction = ''] = normalized.split('.');
  const cents = Number(whole) * 100 + Number(fraction.padEnd(2, '0'));
  if (!Number.isSafeInteger(cents) || cents > 2147483647) throw new Error('El importe es demasiado alto.');
  return cents;
}
export function measurement(value: string | undefined): number | null {
  if (!value?.trim()) return null;
  const normalized = value.trim().replace(',', '.');
  const number = Number(normalized);
  if (!/^\d+(?:\.\d)?$/.test(normalized) || number <= 0 || number > 300) {
    throw new Error('Las medidas deben ser mayores que 0 y hasta 300 cm, con un decimal como máximo.');
  }
  return number;
}
export function productRequest(draft: ProductDraft): ProductCreate {
  const price = priceToCents(draft.price);
  const skus = new Set<string>();
  if (draft.name.trim().length < 2 || draft.name.trim().length > 200) throw new Error('Escribe un nombre de 2 a 200 caracteres.');
  if (draft.slug.length < 2 || draft.slug.length > 200 || !/^[a-z0-9]+(?:-[a-z0-9]+)*$/.test(draft.slug)) throw new Error('Revisa el identificador del producto.');
  if (draft.description.length > 5000 || draft.variants.length > 100 || draft.images.length > 12) throw new Error('Revisa la descripción y el número de variantes o fotos.');
  const variants = draft.variants.map((entry) => {
    const sku = entry.sku.trim();
    if (sku.length < 3 || sku.length > 100 || skus.has(sku)) throw new Error('Cada variante necesita un SKU único de 3 a 100 caracteres.');
    skus.add(sku);
    if (entry.size.trim().length > 50 || entry.color.trim().length > 50) throw new Error('La talla y el color admiten hasta 50 caracteres.');
    const adjustment = priceToCents(entry.adjustment);
    if (price + adjustment > 2147483647) throw new Error('El precio de una variante es demasiado alto.');
    return { sku, size: entry.size.trim() || null, color: entry.color.trim() || null, price_adjustment_cents: adjustment, bust_cm: measurement(entry.bust_cm), waist_cm: measurement(entry.waist_cm), hip_cm: measurement(entry.hip_cm) };
  });
  const colors = new Map(variants.filter((v) => v.color).map((v) => [v.color!.toLocaleLowerCase(), v.color!]));
  const seen = new Set<string>();
  const images = draft.images.map((entry) => {
    const color = entry.color.trim(); const alt = entry.alt.trim();
    if (!entry.url.startsWith('https://')) throw new Error('Selecciona un archivo para cada foto de la galería.');
    if (alt.length < 2 || alt.length > 200 || !color || color.length > 50) throw new Error('Cada foto necesita descripción y color.');
    const normalized = colors.get(color.toLocaleLowerCase());
    if (colors.size && !normalized) throw new Error('El color de cada foto debe coincidir con una variante.');
    const key = `${entry.url}:${color.toLocaleLowerCase()}`;
    if (seen.has(key)) throw new Error('No repitas la misma foto para un color.');
    seen.add(key);
    return { url: entry.url, alt, color: normalized || color };
  });
  if (draft.coverUrl && !draft.coverUrl.startsWith('https://')) throw new Error('La portada debe ser una foto subida correctamente.');
  return { name: draft.name.trim(), slug: draft.slug.trim(), description: draft.description.trim() || null,
    price_cents: price, is_active: draft.is_active, image_url: draft.coverUrl || null, variants, images };
}

function centsToPrice(cents: number): string {
  return `${Math.floor(cents / 100)}.${String(cents % 100).padStart(2, '0')}`;
}
export function productToDraft(product: Product): ProductDraft {
  return {
    name: product.name, slug: product.slug, description: product.description || '',
    price: centsToPrice(product.price_cents), is_active: product.is_active, coverUrl: product.image_url || '',
    variants: product.variants.map((variant) => ({ id: variant.id, sku: variant.sku,
      size: variant.size || '', color: variant.color || '', adjustment: centsToPrice(variant.price_adjustment_cents), bust_cm: variant.bust_cm == null ? '' : String(variant.bust_cm), waist_cm: variant.waist_cm == null ? '' : String(variant.waist_cm), hip_cm: variant.hip_cm == null ? '' : String(variant.hip_cm) })),
    images: (product.images || []).map(({ url, alt, color }) => ({ url, alt, color })),
  };
}
export function productUpdateRequest(draft: ProductDraft): ProductUpdate {
  const request = productRequest(draft);
  return { ...request, variants: request.variants.map((variant, index) => {
    const id = draft.variants[index].id;
    return id === undefined ? variant : { ...variant, id };
  }) };
}
