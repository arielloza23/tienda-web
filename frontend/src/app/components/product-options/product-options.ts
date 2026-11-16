import { CurrencyPipe } from '@angular/common';
import { Component, input, output } from '@angular/core';
import { ProductVariant } from '../../models/product.model';
import { SizeGuide } from '../size-guide/size-guide';

@Component({
  selector: 'app-product-options',
  imports: [CurrencyPipe, SizeGuide],
  templateUrl: './product-options.html',
  styleUrl: './product-options.scss',
})
export class ProductOptions {
  readonly variants = input.required<ProductVariant[]>();
  readonly selectedId = input<number | null>(null);
  readonly productName = input.required<string>();
  readonly selectVariant = output<number>();

  protected variantLabel(variant: ProductVariant): string {
    const size = variant.size?.trim();
    const color = variant.color?.trim();
    return [size ? `Talla ${size}` : 'Talla no especificada', color || 'Color no especificado',
      !size && !color ? variant.sku : ''].filter(Boolean).join(', ');
  }
}
