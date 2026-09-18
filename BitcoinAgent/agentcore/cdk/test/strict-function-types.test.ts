import * as fs from 'fs';
import * as path from 'path';
import * as ts from 'typescript';

test('CDK tsconfig matches TS playground strictFunctionTypes=false', () => {
  const configPath = path.join(__dirname, '..', 'tsconfig.json');
  const text = fs.readFileSync(configPath, 'utf8');
  const parsed = ts.parseConfigFileTextToJson(configPath, text);
  expect(parsed.error).toBeUndefined();
  expect(parsed.config.compilerOptions.strict).toBe(true);
  expect(parsed.config.compilerOptions.strictFunctionTypes).toBe(false);
});
