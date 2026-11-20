import { TestBed } from '@angular/core/testing';
import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { AnalyticsService } from './analytics.service';

describe('Anonymous store measurement', () => {
  let service: AnalyticsService;
  let http: HttpTestingController;
  beforeEach(() => {
    vi.useFakeTimers();
    sessionStorage.clear();
    vi.stubGlobal('navigator', { doNotTrack: '0' });
    TestBed.configureTestingModule({ providers: [provideHttpClient(), provideHttpClientTesting()] });
    service = TestBed.inject(AnalyticsService);
    http = TestBed.inject(HttpTestingController);
  });
  afterEach(() => { http.verify(); TestBed.resetTestingModule(); vi.restoreAllMocks(); vi.unstubAllGlobals(); vi.useRealTimers(); });

  it('batches interactions with allowlisted identifiers and no contact details or page URLs', () => {
    service.track('gallery_open', 7);
    service.track('variant_select', 7, 12);
    http.expectNone(req => req.url.endsWith('/analytics/events'));
    vi.advanceTimersByTime(2000);
    const request = http.expectOne(req => req.url.endsWith('/analytics/events'));
    const events = request.request.body.events;
    expect(events).toHaveLength(2);
    expect(Object.keys(events[0]).sort()).toEqual(['event_id', 'event_type', 'product_id', 'session_id']);
    expect(events[0].session_id).toBe(events[1].session_id);
    expect(events[0].event_id).not.toBe(events[1].event_id);
    expect(events[1].variant_id).toBe(12);
    request.flush({ accepted: 2 });
  });

  it('sends the featured product view promptly before a possible checkout', () => {
    service.track('product_view', 1);
    const request = http.expectOne(req => req.url.endsWith('/analytics/events'));
    expect(request.request.body.events[0].event_type).toBe('product_view');
    request.flush({ accepted: 1 });
  });

  it('records the still-featured product again when activity starts a new session', () => {
    service.track('product_view', 7);
    const first = http.expectOne(req => req.url.endsWith('/analytics/events'));
    const originalSession = first.request.body.events[0].session_id;
    first.flush({ accepted: 1 });
    vi.advanceTimersByTime(30 * 60000);
    service.track('variant_select', 7, 12);
    const resumed = http.expectOne(req => req.url.endsWith('/analytics/events'));
    expect(resumed.request.body.events).toHaveLength(1);
    expect(resumed.request.body.events[0]).toMatchObject({ event_type: 'product_view', product_id: 7 });
    const newSession = resumed.request.body.events[0].session_id;
    expect(newSession).not.toBe(originalSession);
    resumed.flush({ accepted: 1 });
    service.flush();
    const interaction = http.expectOne(req => req.url.endsWith('/analytics/events'));
    expect(interaction.request.body.events[0]).toMatchObject({ event_type: 'variant_select', session_id: newSession });
    interaction.flush({ accepted: 1 });
  });

  it('silently skips measurement when crypto fails, even with an existing session', () => {
    service.sessionId();
    vi.spyOn(crypto, 'randomUUID').mockImplementation(() => { throw new Error('Unavailable'); });
    expect(() => service.track('gallery_open', 1)).not.toThrow();
    service.flush();
    http.expectNone(req => req.url.endsWith('/analytics/events'));
  });

  it('keeps batches bounded and drops failed collection without retrying', () => {
    for (let i = 0; i < 20; i++) service.track('gallery_open', 1);
    const request = http.expectOne(req => req.url.endsWith('/analytics/events'));
    expect(request.request.body.events).toHaveLength(20);
    request.flush({}, { status: 503, statusText: 'Unavailable' });
    vi.advanceTimersByTime(60000);
    http.expectNone(req => req.url.endsWith('/analytics/events'));
  });

  it('rotates sessions after 30 minutes of inactivity while extending active sessions', () => {
    const original = service.sessionId();
    vi.advanceTimersByTime(29 * 60000);
    expect(service.sessionId()).toBe(original);
    vi.advanceTimersByTime(30 * 60000);
    expect(service.sessionId()).not.toBe(original);
  });

  it('continues in memory when browser storage is blocked', () => {
    vi.spyOn(Storage.prototype, 'getItem').mockImplementation(() => { throw new Error('Blocked'); });
    vi.spyOn(Storage.prototype, 'setItem').mockImplementation(() => { throw new Error('Blocked'); });
    const id = service.sessionId();
    expect(id).toMatch(/^[a-f0-9-]{36}$/);
    expect(service.sessionId()).toBe(id);
  });

  it('respects Do Not Track and Global Privacy Control, including queued events', () => {
    service.track('gallery_open', 1);
    vi.stubGlobal('navigator', { doNotTrack: '1' });
    expect(service.sessionId()).toBeUndefined();
    service.flush();
    vi.stubGlobal('navigator', { doNotTrack: '0', globalPrivacyControl: true });
    service.track('add_to_cart', 1);
    vi.advanceTimersByTime(2000);
    http.expectNone(req => req.url.endsWith('/analytics/events'));
  });
});
