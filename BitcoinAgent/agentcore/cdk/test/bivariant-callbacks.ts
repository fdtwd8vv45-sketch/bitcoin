/**
 * Compile-time lock for `strictFunctionTypes: false`.
 *
 * This assignment is accepted with bivariant function parameters and is an
 * error on the TS playground when the flag is enabled:
 * https://www.typescriptlang.org/play/?strictFunctionTypes=false
 */
function takesString(x: string): void {
  void x;
}

type StringOrNumberFunc = (ns: string | number) => void;

export const bivariantCallback: StringOrNumberFunc = takesString;
