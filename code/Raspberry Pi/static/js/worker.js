// worker.js
onmessage = function(e) {
    if (e.data === 'fetchData') {
        fetch('/get_raw')
            .then(response => response.json())
            .then(data => {
                postMessage(data);
            })
            .catch(error => console.error('Error:', error));
    }
}