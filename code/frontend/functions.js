export function generateUUID() { // Public Domain/MIT
    var d = new Date().getTime();//Timestamp
    var d2 = ((typeof performance !== 'undefined') && performance.now && (performance.now() * 1000)) || 0;//Time in microseconds since page-load or 0 if unsupported
    return 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, function (c) {
        var r = Math.random() * 16;//random number between 0 and 16
        if (d > 0) {//Use timestamp until depleted
            r = (d + r) % 16 | 0;
            d = Math.floor(d / 16);
        } else {//Use microseconds since page-load if supported
            r = (d2 + r) % 16 | 0;
            d2 = Math.floor(d2 / 16);
        }
        return (c === 'x' ? r : (r & 0x3 | 0x8)).toString(16);
    });
}

export function generateEventData(eventName, msg) {
    const messageId = generateUUID();

    // Create an object representing the data structure
    const data = {
        events: [{
            event: eventName,
            message_id: messageId,
            msg: msg
        }]
    };

    // Convert the object to JSON format
    const json = JSON.stringify(data);
    return json;
}

export function getNewClientId() {
    const customerShort = "sb-gapcloud";
    const mobileAppId = "Jugal_AscottCubbyChat_UID";
    const baseInfo = [{
        ID: generateUUID(),
        Name: customerShort,
        Scope: `${customerShort}.brightpattern.com`,
        MainUrl: `https://${customerShort}.brightpattern.com`,
        AppId: mobileAppId
    }];

    if (baseInfo[0].ID && typeof baseInfo[0].ID === 'string') {
        console.log(`GUID created for client ${baseInfo[0].ID}.`);
        const authHeader = `MOBILE-API-140-327-PLAIN appId="${baseInfo[0].AppId}", clientId="${baseInfo[0].ID}"`;
        baseInfo[0].Authentication = authHeader;
        return baseInfo[0];
    } else {
        console.log("GUID column does not exist in the output.");
        return null;
    }
}

export async function fetchFirebaseConfig(filename) {
    try {
        const response = await fetch(filename);
        if (!response.ok) {
            throw new Error('Failed to fetch Firebase configuration');
        }
        const config = await response.json();
        return config;
    } catch (error) {
        if (disableFirebase === true) {
            document.getElementById('startChatButton').disabled = false;
            document.getElementById('check_notification_endpointButton').disabled = false;
        }
        console.error('Error fetching Firebase configuration:', error);
        return null;
    }
}
