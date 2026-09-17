"use client";
export default function ErrorPage({ reset }: { reset: () => void }) {
  return (
    <div className="unavailable" role="alert">
      <h1>Something interrupted this view</h1>
      <p>
        Your saved investigation data is unchanged. Try loading the view again.
      </p>
      <button onClick={reset} className="button primary">
        Try again
      </button>
    </div>
  );
}
