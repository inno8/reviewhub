/**
 * Permissive type shim for `useApi.js`.
 *
 * The runtime module is JS (large surface — every Django REST endpoint
 * has a method on `api.*`). Authoring full types for it would be a
 * multi-day refactor that brings limited value when the underlying
 * server-side serializers can change shape independently. Until we
 * port `useApi.js` to TypeScript with shared backend-derived types,
 * this shim lets `.ts` consumers import without `noImplicitAny` errors.
 *
 * Treat all returns as `any` for now; downstream consumers narrow at
 * the call site (or via store-level types).
 */

export declare function setSkipAuthRedirect(skip: boolean): void;
// eslint-disable-next-line @typescript-eslint/no-explicit-any
export declare const api: any;
// eslint-disable-next-line @typescript-eslint/no-explicit-any
export declare function useApi(): any;
