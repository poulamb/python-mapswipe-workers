var database = firebase.database();
function submitInfo() {

    if (currentUid == null) {
      alert("You are not logged in.");
    } else {

    // get basic project information
    var name = document.getElementById("name").value;
    var lookFor = document.getElementById("lookFor").value;
    var projectDetails = document.getElementById("projectDetails").value;
    var projectType = document.getElementById("projectType").value;
    var image = document.getElementById("image").value;
    var verificationNumber = document.getElementById("verificationNumber").value;
    var createdBy = currentUid;
    var groupSize = document.getElementById("groupSize").value;

    if (projectType == 1) {

        var zoomLevel = document.getElementById("zoomLevel").value;
        var kml = document.getElementById("kml").value;
        var tileServer = {
          name: document.getElementById("tileServerBuildArea").value,
          url: document.getElementById("tileServerUrlBuildArea").value,
          wmtsLayerName: document.getElementById("tileServerLayerNameBuildArea").value,
          apiKeyRequired: document.getElementById("apiKeyRequiredBuildArea").value,
          apiKey: document.getElementById("apiKeyBuildArea").value
        };

        var mapswipe_import = {
            name: name,
            lookFor: lookFor,
            projectDetails: projectDetails,
            projectType: projectType,
            image: image,
            verificationNumber: verificationNumber,
            groupSize: groupSize,
            tileServer: tileServer,
            zoomLevel: zoomLevel,
            kml: kml,
            createdBy: createdBy
        }

    } else if (projectType == 2) {

        var inputGeometries = document.getElementById("inputGeometries").value;
        var tileServer = {
          name: document.getElementById("tileServerFootprint").value,
          url: document.getElementById("tileServerUrlFootprint").value,
          wmtsLayerName: document.getElementById("tileServerLayerNameFootprint").value,
          caption: document.getElementById("captionFootprint").value,
          date: document.getElementById("dateFootprint").value
        };

        var mapswipe_import = {
            name: name,
            lookFor: lookFor,
            projectDetails: projectDetails,
            projectType: projectType,
            image: image,
            groupSize: groupSize,
            verificationNumber: verificationNumber,
            tileServer: tileServer,
            createdBy: createdBy,
            inputGeometries: inputGeometries
        }

    } else if (projectType == 3) {

      var zoomLevel = document.getElementById("zoomLevelChangeDetection").value;
      var kml = document.getElementById("kmlChangeDetection").value;
      var tileServerA = {
        name: document.getElementById("tileServerChangeDetectionA").value,
        url: document.getElementById("tileServerUrlChangeDetectionA").value,
        wmtsLayerName: document.getElementById("tileServerLayerNameChangeDetectionA").value,
        apiKeyRequired: document.getElementById("apiKeyRequiredChangeDetectionA").value,
        apiKey: document.getElementById("apiKeyChangeDetectionA").value,
        caption: document.getElementById("captionChangeDetectionA").value,
        date: document.getElementById("dateChangeDetectionA").value
      };
      var tileServerB = {
        name: document.getElementById("tileServerChangeDetectionB").value,
        url: document.getElementById("tileServerUrlChangeDetectionB").value,
        wmtsLayerName: document.getElementById("tileServerLayerNameChangeDetectionB").value,
        apiKeyRequired: document.getElementById("apiKeyRequiredChangeDetectionB").value,
        apiKey: document.getElementById("apiKeyChangeDetectionB").value,
        caption: document.getElementById("captionChangeDetectionB").value,
        date: document.getElementById("dateChangeDetectionB").value
      };

      var mapswipe_import = {
          name: name,
          lookFor: lookFor,
          projectDetails: projectDetails,
          projectType: projectType,
          image: image,
          groupSize: groupSize,
          verificationNumber: verificationNumber,
          tileServerA: tileServerA,
          tileServerB: tileServerB,
          zoomLevel: zoomLevel,
          kml: kml,
          createdBy: createdBy
      }

    }

    firebase.database().ref('v2/projectDrafts/').push().set(mapswipe_import)
          .then(function() {
            clear_all_fields();
            displaySuccessMessage();
          })
          .catch(function(error) {
            alert('could not upload data: ' + error);
          });

  }
}
