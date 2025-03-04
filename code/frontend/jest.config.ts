import type { Config } from '@jest/types'

const config: Config.InitialOptions = {
  preset: 'ts-jest',
  testEnvironment: 'jest-environment-jsdom',
  moduleNameMapper: {
    '\\.(css|less|sass|scss)$': 'identity-obj-proxy',
    '\\.(jpg|jpeg|png|gif|svg)$': '<rootDir>/__mocks__/fileMock.js',
    '^lodash-es$': 'lodash',
  },
  setupFilesAfterEnv: ['<rootDir>/setupTests.ts'],
  testMatch: ['**/?(*.)+(spec|test).[jt]s?(x)'],
  transform: {
    '^.+\\.[tj]sx?$': 'ts-jest',
  },
  transformIgnorePatterns: [
    '/node_modules/(?!react-markdown|vfile|unist-util-stringify-position|unist-util-visit|bail|is-plain-obj)',
  ],
  collectCoverageFrom: ['src/**/*.{ts,tsx,js,jsx}'],
  coveragePathIgnorePatterns: [
    '<rootDir>/node_modules/', // Ignore node_modules
    '<rootDir>/__mocks__/', // Ignore mocks
    '<rootDir>/src/api/',
    '<rootDir>/src/mocks/',
    '<rootDir>/src/test/',
    '<rootDir>/src/index.tsx',
    '<rootDir>/src/vite-env.d.ts',
    '<rootDir>/src/components/QuestionInput/index.ts',
    '<rootDir>/src/components/Answer/index.ts',
    '<rootDir>/src/components/Utils/utils.tsx',
  ],
};

export default config;
