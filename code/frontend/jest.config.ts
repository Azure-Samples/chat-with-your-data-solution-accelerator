import type { Config } from '@jest/types';

const config: Config.InitialOptions = {
verbose: true,
preset: 'ts-jest',
testEnvironment: "jest-environment-jsdom",
testEnvironmentOptions: {
customExportConditions: [''],
},

moduleNameMapper: {
    'microsoft-cognitiveservices-speech-sdk':'<rootDir>/__mocks__/microsoft-cognitiveservices-speech-sdk.ts',
    '\\.(css|less|scss|svg|png|jpg)$': 'identity-obj-proxy',

},
transformIgnorePatterns: [
    '/node_modules/(?!react-markdown|vfile|unist-util-stringify-position|unist-util-visit|bail|is-plain-obj)',
  ],
setupFilesAfterEnv: ['<rootDir>/src/test/setupTests.ts'], // For setting up testing environment like jest-dom
transform: {
'^.+\\.(ts|tsx)$': 'ts-jest',
},

setupFiles: ['<rootDir>/jest.polyfills.js'],
};

export default config;
