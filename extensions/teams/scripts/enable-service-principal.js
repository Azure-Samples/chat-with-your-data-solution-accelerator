// Script to create a service principal for the Microsoft Entra application
const { exec } = require('child_process');
const util = require('util');
const execPromise = util.promisify(exec);

async function createServicePrincipal() {
  const appId = process.env.BOT_ID;
  
  if (!appId) {
    console.error('Error: BOT_ID environment variable is not set');
    process.exit(1);
  }
  
  console.log(`Creating service principal for AAD application with ID: ${appId}`);
  
  try {
    // Check if Azure CLI is installed and logged in
    await execPromise('az account show');
    
    // Check if service principal already exists
    const checkCmd = `az ad sp list --filter "appId eq '${appId}'"`;
    const { stdout } = await execPromise(checkCmd);
    
    const existingSpList = JSON.parse(stdout);
    if (existingSpList && existingSpList.length > 0) {
      console.log(`Service principal for application ID ${appId} already exists. Skipping creation.`);
      process.exit(0);
    }
    
    // Create service principal
    const createCmd = `az ad sp create --id "${appId}"`;
    await execPromise(createCmd);
    
    console.log('Service principal created successfully.');
  } catch (error) {
    console.error('Error:', error.message);
    if (error.message.includes('az: not found') || error.message.includes('not recognized as an internal or external command')) {
      console.error('Azure CLI is not installed or not in PATH. Please install it first.');
    } else if (error.message.includes('Please run az login')) {
      console.error('You are not logged into Azure. Please run az login first.');
    } else {
      console.error('Failed to create service principal. Please ensure you have the right permissions.');
    }
    process.exit(1);
  }
}

createServicePrincipal();
