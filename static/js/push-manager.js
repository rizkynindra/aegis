/**
 * AEGIS Push Notification Manager
 * Handles Service Worker registration, permission requests, and VAPID subscription.
 */

async function initPushNotifications() {
    if (!('serviceWorker' in navigator) || !('PushManager' in window)) {
        console.log('Push notifications are not supported in this browser.');
        return;
    }

    try {
        const registration = await navigator.serviceWorker.ready;
        
        // Check if we already have a subscription
        let subscription = await registration.pushManager.getSubscription();
        
        if (!subscription) {
            console.log('No push subscription found. Requesting permission...');
            const permission = await Notification.requestPermission();
            
            if (permission !== 'granted') {
                console.log('Notification permission denied.');
                return;
            }

            // Get public key from server
            const response = await fetch('/api/vapid-public-key');
            const { publicKey } = await response.json();

            // Subscribe the user
            subscription = await registration.pushManager.subscribe({
                userVisibleOnly: true,
                applicationServerKey: urlBase64ToUint8Array(publicKey)
            });

            // Send subscription to backend
            await fetch('/api/subscribe', {
                method: 'POST',
                body: JSON.stringify(subscription),
                headers: { 'Content-Type': 'application/json' }
            });
            console.log('Push notification subscription successful.');
        } else {
            // Refresh subscription on backend just in case
            await fetch('/api/subscribe', {
                method: 'POST',
                body: JSON.stringify(subscription),
                headers: { 'Content-Type': 'application/json' }
            });
            console.log('Push subscription verified and refreshed.');
        }
    } catch (err) {
        console.error('Push registration failed:', err);
    }
}

function urlBase64ToUint8Array(base64String) {
    const padding = '='.repeat((4 - base64String.length % 4) % 4);
    const base64 = (base64String + padding)
        .replace(/\-/g, '+')
        .replace(/_/g, '/');

    const rawData = window.atob(base64);
    const outputArray = new Uint8Array(rawData.length);

    for (let i = 0; i < rawData.length; ++i) {
        outputArray[i] = rawData.charCodeAt(i);
    }
    return outputArray;
}

// Automatically init based on DOM ready if needed, 
// or export to be called by dashboard scripts.
window.addEventListener('load', () => {
    // Small delay to ensure SW is fully ready
    setTimeout(initPushNotifications, 1000);
});
