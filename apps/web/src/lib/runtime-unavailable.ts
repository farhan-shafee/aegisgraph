export class RuntimeUnavailableError extends Error {
  readonly retryAfter: string | undefined;

  constructor(retryAfter?: string | null) {
    super("Public demo service configuration is unavailable.");
    this.retryAfter =
      retryAfter && /^\d{1,6}$/.test(retryAfter) ? retryAfter : undefined;
  }
}
