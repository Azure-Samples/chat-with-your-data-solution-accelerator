import "@testing-library/jest-dom";
const { TextDecoder, TextEncoder } = require('node:util')

import { initializeIcons } from "@fluentui/react/lib/Icons";
initializeIcons();
global.TextEncoder = TextEncoder;
global.TextDecoder = TextDecoder;
