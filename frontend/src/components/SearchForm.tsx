import { useState } from "react";
import { searchRoutes, type RouteSearchParams } from "../services/api";
import type { RouteSearchResponse } from "../types";
import { StationModeSelect } from "./StationModeSelect";

const SEARCH_TIMEOUT_MS = 10_000;
const MAX_ADVANCE_DAYS = 30;

function toDatetimeLocalValue(date: Date): string {
  const pad = (n: number) => String(n).padStart(2, "0");
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}T${pad(date.getHours())}:${pad(
    date.getMinutes(),
  )}`;
}

interface Props {
  onResults: (result: RouteSearchResponse, params: RouteSearchParams) => void;
}

export function SearchForm({ onResults }: Props) {
  const now = new Date();
  const maxDate = new Date(now.getTime() + MAX_ADVANCE_DAYS * 24 * 60 * 60 * 1000);

  const [originId, setOriginId] = useState<string | null>(null);
  const [destinationId, setDestinationId] = useState<string | null>(null);
  const [departureTime, setDepartureTime] = useState(toDatetimeLocalValue(now));
  const [errors, setErrors] = useState<{ origin?: string; destination?: string }>({});
  const [isLoading, setIsLoading] = useState(false);
  const [timedOut, setTimedOut] = useState(false);
  const [submitError, setSubmitError] = useState<string | null>(null);

  function validate(): boolean {
    const nextErrors: { origin?: string; destination?: string } = {};
    if (!originId) nextErrors.origin = "此欄位為必填";
    if (!destinationId) nextErrors.destination = "此欄位為必填";
    if (originId && destinationId && originId === destinationId) {
      nextErrors.origin = "起點與終點不得相同";
      nextErrors.destination = "起點與終點不得相同";
    }
    setErrors(nextErrors);
    return Object.keys(nextErrors).length === 0;
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setSubmitError(null);
    setTimedOut(false);
    if (!validate()) return;

    setIsLoading(true);
    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), SEARCH_TIMEOUT_MS);

    const params: RouteSearchParams = {
      origin: originId!,
      destination: destinationId!,
      departure_time: new Date(departureTime).toISOString(),
    };

    try {
      const result = await searchRoutes(params);
      onResults(result, params);
    } catch (err: unknown) {
      if (axiosIsAbortOrTimeout(err)) {
        setTimedOut(true);
      } else {
        setSubmitError(extractErrorMessage(err));
      }
    } finally {
      clearTimeout(timeoutId);
      setIsLoading(false);
    }
  }

  return (
    <form className="search-form" onSubmit={handleSubmit}>
      <StationModeSelect label="起點" onChange={setOriginId} errorMessage={errors.origin} />
      <StationModeSelect label="終點" onChange={setDestinationId} errorMessage={errors.destination} />
      <label>
        出發時間
        <input
          type="datetime-local"
          value={departureTime}
          min={toDatetimeLocalValue(now)}
          max={toDatetimeLocalValue(maxDate)}
          onChange={(e) => setDepartureTime(e.target.value)}
        />
      </label>
      <button type="submit" disabled={isLoading}>
        {isLoading ? "查詢中..." : "查詢路線"}
      </button>
      {isLoading && <p role="status">載入中，請稍候...</p>}
      {timedOut && (
        <p role="alert" className="timeout-message">
          查詢逾時，請重試
        </p>
      )}
      {submitError && (
        <p role="alert" className="submit-error">
          {submitError}
        </p>
      )}
    </form>
  );
}

function axiosIsAbortOrTimeout(err: unknown): boolean {
  if (typeof err !== "object" || err === null) return false;
  const code = (err as { code?: string }).code;
  const name = (err as { name?: string }).name;
  return code === "ECONNABORTED" || name === "CanceledError" || name === "AbortError";
}

function extractErrorMessage(err: unknown): string {
  if (typeof err === "object" && err !== null) {
    const response = (err as { response?: { data?: { message?: string } } }).response;
    if (response?.data?.message) return response.data.message;
  }
  return "查詢失敗，請稍後再試";
}
