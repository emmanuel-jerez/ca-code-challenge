/** Makes a switch over a union fail to compile when a new member is unhandled. */
export function assertNever(value: never): never {
  throw new Error(`Unhandled value: ${JSON.stringify(value)}`);
}
