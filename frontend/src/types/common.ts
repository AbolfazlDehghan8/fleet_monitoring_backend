/**
 * The backend's list endpoints are plain (non-paginated) JSON arrays — there is no
 * DRF pagination envelope in practice, even though PageNumberPagination is configured
 * globally (it is simply unused by these APIView-based endpoints). Several endpoints
 * apply a hard server-side cap (e.g. 500 telemetry logs, 200 reports) instead.
 */
export type ApiList<T> = T[];

/** Generic shape of a DRF / Django ValidationError response body. */
export type ApiErrorBody =
  | { detail: string }
  | { detail: string[] }
  | Record<string, string[] | string>;

export class ApiError extends Error {
  status: number;
  body: ApiErrorBody | undefined;

  constructor(status: number, body: ApiErrorBody | undefined, message?: string) {
    super(message ?? ApiError.extractMessage(body) ?? `Request failed with status ${status}`);
    this.name = 'ApiError';
    this.status = status;
    this.body = body;
  }

  static extractMessage(body: ApiErrorBody | undefined): string | undefined {
    if (!body) return undefined;
    if ('detail' in body && body.detail) {
      return Array.isArray(body.detail) ? body.detail.join(' ') : body.detail;
    }
    const firstKey = Object.keys(body)[0];
    if (!firstKey) return undefined;
    const value = (body as Record<string, string[] | string>)[firstKey];
    const text = Array.isArray(value) ? value.join(' ') : value;
    return `${firstKey}: ${text}`;
  }
}
