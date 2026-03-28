async function buyVideo(videoId){

    const response = await fetch("/api/buy-video/",{

        method:"POST",

        headers:{
            "Content-Type":"application/json"
        },

        body:JSON.stringify({
            video_id:videoId
        })

    })

    const data = await response.json()

    if(data.success){

        const player = document.getElementById("video-player")

        player.src = data.video_url

        document.getElementById("video-container").style.display="block"

    }else{

        alert(data.message)

    }
}