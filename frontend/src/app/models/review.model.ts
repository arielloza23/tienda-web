export interface CustomerUser { id: number; full_name: string; email: string; role: string; is_active: boolean; }
export interface ReviewRead { id: number; product_id: number; author_name: string; rating: number; comment: string | null; created_at: string; updated_at: string; }
export interface ReviewPage { items: ReviewRead[]; total: number; average_rating: number | null; limit: number; offset: number; }
