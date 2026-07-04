import { AxiosError } from "axios";
import type { AxiosResponse } from "axios";
import type { BlockchainApiResponse, BlockchainErrorResponse } from "../types/blockchain";
import type { ForensicsEnvelope, ForensicsErrorResponse } from "../types/forensics";

/**
 * The backend speaks four response "dialects" (see Frontend Development
 * Plan). Every domain service file funnels its Axios call through one of
 * the normalizers below so callers only ever deal with NormalizedResult.
 */

export interface NormalizedError {
  message: string;
  code?: string;
  details?: Record<string, unknown> | null;
  status?: number;
}

export interface NormalizedResult<T> {
  ok: boolean;
  data: T | null;
  error: NormalizedError | null;
}

function ok<T>(data: T): NormalizedResult<T> {
  return { ok: true, data, error: null };
}

function fail<T>(error: NormalizedError): NormalizedResult<T> {
  return { ok: false, data: null, error };
}

/** Generic catch-all for network failures, timeouts, and unrecognized shapes. */
export function fromAxiosError(err: unknown, fallbackMessage = "Request failed"): NormalizedError {
  if (err instanceof AxiosError) {
    const status = err.response?.status;
    const body = err.response?.data as Record<string, unknown> | undefined;

    if (body && typeof body === "object") {
      if (typeof body.detail === "string") {
        return { message: body.detail, status };
      }
      if (Array.isArray(body.detail)) {
        const messages = body.detail
          .map((item) =>
            item && typeof item === "object" && "msg" in item ? String((item as { msg: unknown }).msg) : null,
          )
          .filter((msg): msg is string => Boolean(msg));
        if (messages.length > 0) {
          return { message: messages.join("; "), status };
        }
      }
      if (typeof body.message === "string") {
        return {
          message: body.message,
          code: typeof body.errorCode === "string" ? body.errorCode : undefined,
          details: (body.details as Record<string, unknown> | null) ?? null,
          status,
        };
      }
    }

    return { message: err.message || fallbackMessage, status };
  }

  if (err instanceof Error) {
    return { message: err.message };
  }

  return { message: fallbackMessage };
}

/** Dialect A — core resources: raw body on success, {detail} on error. */
export async function normalizeCore<T>(promise: Promise<AxiosResponse<T>>): Promise<NormalizedResult<T>> {
  try {
    const response = await promise;
    return ok(response.data);
  } catch (err) {
    return fail(fromAxiosError(err));
  }
}

/** Dialect B — blockchain layer: uniform camelCase envelope. */
export async function normalizeBlockchain<T>(
  promise: Promise<AxiosResponse<BlockchainApiResponse<T>>>,
): Promise<NormalizedResult<T>> {
  try {
    const response = await promise;
    return ok(response.data.data);
  } catch (err) {
    if (err instanceof AxiosError && err.response?.data) {
      const body = err.response.data as BlockchainErrorResponse;
      if (typeof body.message === "string") {
        return fail({
          message: body.message,
          code: body.errorCode,
          details: body.details,
          status: err.response.status,
        });
      }
    }
    return fail(fromAxiosError(err));
  }
}

/** Dialect C — forensics / threat-intel: snake_case envelope, same error shape as blockchain. */
export async function normalizeForensics<T>(
  promise: Promise<AxiosResponse<ForensicsEnvelope<T>>>,
): Promise<NormalizedResult<T>> {
  try {
    const response = await promise;
    return ok(response.data.data);
  } catch (err) {
    if (err instanceof AxiosError && err.response?.data) {
      const body = err.response.data as ForensicsErrorResponse;
      if (typeof body.message === "string") {
        return fail({
          message: body.message,
          code: body.errorCode,
          details: body.details,
          status: err.response.status,
        });
      }
    }
    return fail(fromAxiosError(err));
  }
}

/** Dialect D — dashboard / analytics / timeline: typed body at the top level, no "data" wrapper. */
export async function normalizeDashboard<T>(promise: Promise<AxiosResponse<T>>): Promise<NormalizedResult<T>> {
  try {
    const response = await promise;
    return ok(response.data);
  } catch (err) {
    return fail(fromAxiosError(err));
  }
}
