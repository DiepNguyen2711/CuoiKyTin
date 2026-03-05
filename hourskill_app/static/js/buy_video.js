document.addEventListener("DOMContentLoaded", function () {

    const buyBtn = document.getElementById("buyBtn");

    if (!buyBtn) return;

    buyBtn.addEventListener("click", function () {

        const courseId = buyBtn.dataset.course;

        fetch("/api/buy-video/", {
            method: "POST",
            headers: {
                "Content-Type": "application/json",
                "X-CSRFToken": getCookie("csrftoken")
            },
            body: JSON.stringify({
                course_id: courseId
            })
        })
        .then(response => response.json())
        .then(data => {

            if (data.success) {
                alert("Mua thành công!");

                const player = document.getElementById("videoPlayer");
                player.style.display = "block";

            } else {
                alert(data.message);
            }

        })
        .catch(error => {
            console.error(error);
            alert("Lỗi kết nối mạng, vui lòng thử lại!");
        });

    });

});


function getCookie(name) {
    let cookieValue = null;

    if (document.cookie && document.cookie !== "") {

        const cookies = document.cookie.split(";");

        for (let i = 0; i < cookies.length; i++) {

            const cookie = cookies[i].trim();

            if (cookie.substring(0, name.length + 1) === (name + "=")) {

                cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
                break;

            }
        }
    }

    return cookieValue;
}