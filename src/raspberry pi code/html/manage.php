<!doctype html>

<html lang="en">

<head>
	<meta charset="utf-8">
	<meta http-equiv="X-UA-Compatible" content="IE=edge">
	<meta name="description" content="Delta5 VTX Timer.">
	<meta name="viewport" content="width=device-width, initial-scale=1.0, minimum-scale=1.0">
	<title>Manage - Delta5 VTX Timer</title>

	<!-- Page styles -->
	<link rel="stylesheet" href="mdl/material.min.css">
	<script src="mdl/material.min.js"></script>
	<link rel="stylesheet" href="https://fonts.googleapis.com/icon?family=Material+Icons">
	
	<link rel="stylesheet" href="styles.css">
	<script type="text/javascript" src="/scripts/jquery-3.1.1.js"></script>
		
	<?php
	if (isset($_POST['startRace'])) {exec("sudo python /home/pi/VTX/startRace.py");	}
	if (isset($_POST['stopRace'])) {exec("sudo python /home/pi/VTX/stopRace.py"); }
	if (isset($_POST['saveLaps'])) {
		exec("sudo python /home/pi/VTX/saveLaps.py");
		exec("sudo python /home/pi/VTX/clearLaps.py"); # after saving the laps then clear currentLaps
	}
	if (isset($_POST['clearLaps']))	{exec("sudo python /home/pi/VTX/clearLaps.py");	}
	?>
</head>
	
<body>
<div class="mdl-layout mdl-js-layout mdl-layout--fixed-header">

<header class="delta5-header mdl-layout__header">
<div class="delta5-navigation mdl-layout__header-row">

	<nav class="mdl-navigation">
		<a class="delta5-navigation mdl-navigation__link" href="index.php"><button class="delta5-navigation mdl-button mdl-js-button mdl-button--raised mdl-js-ripple-effect mdl-button--colored">Races</button></a>
		<a class="delta5-navigation mdl-navigation__link" href="pilots.php"><button class="delta5-navigation mdl-button mdl-js-button mdl-button--raised mdl-js-ripple-effect mdl-button--colored">Pilots</button></a>
		<a class="delta5-navigation mdl-navigation__link" href="groups.php"><button class="delta5-navigation mdl-button mdl-js-button mdl-button--raised mdl-js-ripple-effect mdl-button--colored">Groups</button></a>
		<a class="delta5-navigation mdl-navigation__link" href="manage.php"><button class="delta5-navigation mdl-button mdl-js-button mdl-button--raised mdl-js-ripple-effect mdl-button--accent">Manage</button></a>
		<a class="delta5-navigation mdl-navigation__link" href="settings.php"><button class="delta5-navigation mdl-button mdl-js-button mdl-button--raised mdl-js-ripple-effect mdl-button--colored">Settings</button></a>
	</nav>
	
	<div class="mdl-layout-spacer"></div>
	
	<nav class="mdl-navigation">
		<a class="delta5-navigation mdl-navigation__link" href="setup.php"><button class="delta5-navigation mdl-button mdl-js-button mdl-button--raised mdl-js-ripple-effect mdl-button--colored">Setup</button></a>
	</nav>
	
	<span class="mdl-layout-title">
		<img src="images/delta5fpv.jpg">
	</span>
	
</div>
</header>

<main class="mdl-layout__content">
<div class="page-content">


<div class="mdl-grid"><div class="mdl-cell mdl-cell--12-col">
<form method="post">
<button class="mdl-button mdl-js-button mdl-button--raised mdl-js-ripple-effect" name="startRace">Start Race</button>&nbsp;
<button class="mdl-button mdl-js-button mdl-button--raised mdl-js-ripple-effect" name="stopRace">Stop Race</button>&nbsp;
<button class="mdl-button mdl-js-button mdl-button--raised mdl-js-ripple-effect" name="saveLaps">Save Laps</button>&nbsp;
<button class="mdl-button mdl-js-button mdl-button--raised mdl-js-ripple-effect" name="clearLaps">Clear Laps</button>
</form>
</div></div>


<div id="raceStatus">
<script type="text/javascript">
$(document).ready(function() { setInterval(function() { $('#raceStatus').load('buildRaceStatus.php') }, 1000); } );
</script>
</div>


<div><h5>Leaderboard</h5></div>
<div class="mdl-grid" id="leaderboard">
	<script type="text/javascript">
	$(document).ready(function() { setInterval(function() { $('#leaderboard').load('buildLeaderboardTable.php') }, 2000); } );
	</script>
</div>


<div><h5>Laps</h5></div>
<div class="mdl-grid" id="currentLaps">
	<script type="text/javascript">
	$(document).ready(function() { setInterval(function() { $('#currentLaps').load('buildLapTables.php') }, 1000); } );
	</script>
</div>


<footer class="delta5-footer mdl-mini-footer">
</footer>

</div>
</main>

</div>
</body>

</html>
