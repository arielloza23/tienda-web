import { HttpClient } from '@angular/common/http';
import { DestroyRef, inject, Injectable } from '@angular/core';
import { environment } from '../../environments/environment';

export type AnalyticsEventType = 'product_view' | 'variant_select' | 'gallery_open' | 'reviews_open'
  | 'add_to_cart' | 'checkout_start' | 'whatsapp_click' | 'filter_apply';
export type AnalyticsTarget = 'size' | 'color' | 'price' | 'sort' | 'clear';
interface AnalyticsEvent {
  event_id: string;
  session_id: string;
  event_type: AnalyticsEventType;
  product_id?: number;
  variant_id?: number;
  target?: AnalyticsTarget;
}

/** First-party aggregate measurement: never collect contact details, URLs or free text. */
@Injectable({ providedIn: 'root' })
export class AnalyticsService {
  private readonly http = inject(HttpClient, { optional: true });
  private readonly storageKey = 'tienda.analytics.session';
  private readonly idleMs = 30 * 60 * 1000;
  private session: { id: string; lastActivity: number } | null = null;
  private queue: AnalyticsEvent[] = [];
  private featuredProductId?: number;
  private viewedSessionKey?: string;
  private timer?: ReturnType<typeof setTimeout>;
  private readonly onHidden = () => { if (document.visibilityState === 'hidden') this.flush(); };

  constructor() {
    if (typeof document !== 'undefined') document.addEventListener('visibilitychange', this.onHidden);
    inject(DestroyRef).onDestroy(() => {
      clearTimeout(this.timer);
      if (typeof document !== 'undefined') document.removeEventListener('visibilitychange', this.onHidden);
    });
  }

  sessionId(): string | undefined {
    if (typeof navigator === 'undefined' || navigator.doNotTrack === '1'
      || (navigator as Navigator & { globalPrivacyControl?: boolean }).globalPrivacyControl) return undefined;
    const now = Date.now();
    if (!this.session) {
      try {
        const saved = JSON.parse(sessionStorage.getItem(this.storageKey) || 'null');
        if (saved && typeof saved.id === 'string' && /^[a-f0-9]{8}(-[a-f0-9]{4}){3}-[a-f0-9]{12}$/i.test(saved.id)
          && Number.isFinite(saved.lastActivity)) this.session = saved;
      } catch { /* Storage can be blocked in private browsing. Keep an in-memory session. */ }
    }

    if (!this.session || now - this.session.lastActivity >= this.idleMs || now < this.session.lastActivity) {
      const id = this.uuid();
      if (!id) return undefined;
      this.session = { id, lastActivity: now };
    }
    this.session.lastActivity = now;
    try { sessionStorage.setItem(this.storageKey, JSON.stringify(this.session)); } catch { /* Optional storage. */ }
    this.ensureFeaturedView(this.session.id);
    return this.session.id;
  }

  track(eventType: AnalyticsEventType, productId?: number, variantId?: number, target?: AnalyticsTarget): void {
    if (eventType === 'product_view') this.featuredProductId = productId;
    const sessionId = this.sessionId();
    if (!sessionId || eventType === 'product_view') return;
    const eventId = this.uuid();
    if (!eventId) return;
    // Construct a strict allowlist payload: callers cannot attach arbitrary personal information.
    this.queue.push({ event_id: eventId, session_id: sessionId, event_type: eventType,
      ...(productId ? { product_id: productId } : {}), ...(variantId ? { variant_id: variantId } : {}),
      ...(target ? { target } : {}) });
    if (this.queue.length >= 20) this.flush();
    else if (!this.timer) this.timer = setTimeout(() => this.flush(), 2000);
  }

  setFeaturedProduct(productId: number | undefined): void {
    this.featuredProductId = productId;
    if (productId) this.sessionId();
  }

  private uuid(): string | undefined {
    try { return typeof crypto !== 'undefined' && typeof crypto.randomUUID === 'function' ? crypto.randomUUID() : undefined; }
    catch { return undefined; }
  }

  private ensureFeaturedView(sessionId: string): void {
    if (!this.featuredProductId) return;
    const key = `${sessionId}:${this.featuredProductId}`;
    if (this.viewedSessionKey === key) return;
    const eventId = this.uuid();
    if (!eventId) return;
    this.viewedSessionKey = key;
    this.queue.push({ event_id: eventId, session_id: sessionId, event_type: 'product_view', product_id: this.featuredProductId });
    this.flush();
  }

  flush(): void {
    clearTimeout(this.timer);
    this.timer = undefined;
    if (typeof navigator === 'undefined' || navigator.doNotTrack === '1' || (navigator as Navigator & { globalPrivacyControl?: boolean }).globalPrivacyControl) {
      this.queue = [];
      return;
    }
    if (!this.queue.length) return;
    const events = this.queue.splice(0, 20);
    // No retries or checkout dependency: measurement must never prevent a purchase.
    try {
      this.http?.post(`${environment.apiBaseUrl}/analytics/events`, { events }, { keepalive: true })
        .subscribe({ error: () => {} });
    } catch { /* Optional measurement must not interrupt a native link or checkout. */ }
  }
}
