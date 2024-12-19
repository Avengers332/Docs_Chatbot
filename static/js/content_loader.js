$(document).ready(function () {
    $(document).on('click','#Dashboard',function(){
            var url =  "dashboard"
            function loadContent(url) {
                $("#content").load(url);
            }
            loadContent(url)

    })
 

})