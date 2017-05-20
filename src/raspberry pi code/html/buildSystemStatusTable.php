<?php 
$conn = new mysqli('localhost', 'root', 'delta5fpv', 'vtx');
if ($conn->connect_error) {	die("Connection error: " . $conn->connect_error); }

$results = $conn->query("SELECT `systemStatus`, `raceStatus` FROM `status`") or die($conn->error());
$status = $results->fetch_assoc();
$results = $conn->query("SELECT `minLapTime` FROM `config`") or die($conn->error());
$config = $results->fetch_assoc();
?>

<table class="delta5-table mdl-data-table mdl-js-data-table mdl-shadow--2dp">
<tbody>
<tr>
	<td>System:</td>
	<td>
		<?php
		if ($status['systemStatus'] == 0) {
			echo "Stopped";
		} else {
			echo "Started";
		}
		?>
	</td>
</tr>
<tr>
	<td>Race:</td>
	<td>
		<?php
		if ($status['raceStatus'] == 0) {
			echo "Stopped";
		} else {
			echo "Started";
		}
		?>
	</td>
</tr>
<tr>
	<td>Min Lap Time:</td>
	<td>
		<?php echo $config['minLapTime']; ?>
	</td>
</tr>
</tbody>
</table>
