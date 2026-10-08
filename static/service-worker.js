// ==========================================
// ADMIN PUSH SERVICE WORKER
// ==========================================

self.addEventListener("push", function(event) {

    let data = {};

    try {

        if (event.data) {
            data = event.data.json();
        }

    } catch (error) {

        console.log(
            "Push data error:",
            error
        );

    }


    const title =
        data.title ||
        "New Order Received";


    const options = {

        body:
            data.body ||
            "A new customer order has been received.",

        tag:
            data.tag ||
            "new-order",

        requireInteraction: true,

        data: {
            url:
                data.url ||
                "/admin/orders"
        }

    };


    event.waitUntil(

        self.registration.showNotification(
            title,
            options
        )

    );

});


// ==========================================
// NOTIFICATION CLICK
// ==========================================

self.addEventListener(
    "notificationclick",
    function(event) {

        event.notification.close();


        const url =
            event.notification.data &&
            event.notification.data.url
                ? event.notification.data.url
                : "/admin/orders";


        event.waitUntil(

            clients.matchAll({

                type: "window",
                includeUncontrolled: true

            })

            .then(function(clientList) {

                for (
                    const client
                    of clientList
                ) {

                    if (
                        "focus" in client &&
                        client.url.includes(
                            "/admin/orders"
                        )
                    ) {

                        return client.focus();

                    }

                }


                if (
                    clients.openWindow
                ) {

                    return clients.openWindow(
                        url
                    );

                }

            })

        );

    }
);