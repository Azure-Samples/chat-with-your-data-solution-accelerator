// src/mocks/server.ts 
import { setupServer } from 'msw/node'; 
import { handlers } from './handlers'; 

export const server = setupServer(...handlers); 