<?php

function views($bms_type) {
    $output = "views:\n";
    if ($bms_type == 'JK_PB') {
        $output .= "  - title: Gobel Battery JK\n";
    } else {
        $output .= "  - title: Gobel Battery\n";
    }
    $output .= "    type: sidebar\n";
    $output .= "    cards:\n";
    $output .= "      - show_name: true\n";
    $output .= "        show_icon: true\n";
    $output .= "        show_state: true\n";
    return $output;
}

function glance($device_name, $bms_type) {
  $output = "        type: glance\n";
  $output .= "        entities:\n";
  $output .= "          - entity: sensor.".$device_name."_total_soc\n";
  $output .= "            name: SOC\n";
  $output .= "          - entity: sensor.".$device_name."_total_voltage\n";
  $output .= "            name: Voltage\n";
  $output .= "          - entity: sensor.".$device_name."_total_current\n";
  $output .= "            name: Current\n";
  $output .= "          - entity: sensor.".$device_name."_total_power\n";
  $output .= "            name: Power\n";
  $output .= "        columns: 4\n";
  return $output;
}

function pack_warn_entity_filter($device_name, $total_packs_num, $bms_type, $jk_display_index_start = '01') {
  $output = "";
  for ($i = 0; $i < $total_packs_num; $i++) {
    $display_i = ($bms_type == 'JK_PB' && ($jk_display_index_start == '00' || $jk_display_index_start == '0')) ? $i : $i + 1;
    $pack_str = "pack_" . sprintf("%02d", $display_i);
    $output .= "      - type: entity-filter\n";
    $output .= "        card:\n";
    $output .= "          type: entities\n";
    $output .= "          title: Pack " . sprintf("%02d", $display_i) . " Warning\n";
    $output .= "        conditions:\n";
    $output .= "          - condition: state\n";
    $output .= "            state: 'on'\n";
    $output .= "        show_empty: false\n";
    $output .= "        view_layout:\n";
    $output .= "          position: sidebar\n";
    $output .= "        entities:\n";
    
    $entity_prefix = "binary_sensor." . $device_name . "_" . $pack_str . "_";
    
    $output .= "          - entity: " . $entity_prefix . "short_circuit_protection\n";
    $output .= "            name: Short Circuit Protection\n";
    $output .= "          - entity: " . $entity_prefix . "discharge_overcurrent_protection\n";
    $output .= "            name: Discharge Overcurrent Protection\n";
    $output .= "          - entity: " . $entity_prefix . "charge_overcurrent_protection\n";
    $output .= "            name: Charge Overcurrent Protection\n";
    $output .= "          - entity: " . $entity_prefix . "total_under_voltage_protection\n";
    $output .= "            name: Total Under-Voltage Protection\n";
    $output .= "          - entity: " . $entity_prefix . "total_over_voltage_protection\n";
    $output .= "            name: Total Over-Voltage Protection\n";
    $output .= "          - entity: " . $entity_prefix . "cell_under_voltage_protection\n";
    $output .= "            name: Cell Under-Voltage Protection\n";
    $output .= "          - entity: " . $entity_prefix . "cell_over_voltage_protection\n";
    $output .= "            name: Cell Over-Voltage Protection\n";
    $output .= "          - entity: " . $entity_prefix . "charge_low_temp_protection\n";
    $output .= "            name: Charge Low Temp Protection\n";
    $output .= "          - entity: " . $entity_prefix . "charge_high_temp_protection\n";
    $output .= "            name: Charge High Temp Protection\n";
    $output .= "          - entity: " . $entity_prefix . "mos_high_temp_protection\n";
    $output .= "            name: MOS High Temp Protection\n";
    $output .= "          - entity: " . $entity_prefix . "discharge_high_temp_protection\n";
    $output .= "            name: Discharge High Temp Protection\n";
    $output .= "          - entity: " . $entity_prefix . "low_env_temp_protection\n";
    $output .= "            name: Low Env Temp Protection\n";
    $output .= "          - entity: " . $entity_prefix . "high_env_temp_protection\n";
    $output .= "            name: High Env Temp Protection\n";
    $output .= "          - entity: " . $entity_prefix . "discharge_low_temp_protection\n";
    $output .= "            name: Discharge Low Temp Protection\n";
    $output .= "          - entity: " . $entity_prefix . "sampling_fault\n";
    $output .= "            name: Sampling Fault\n";
    $output .= "          - entity: " . $entity_prefix . "cell_count_mismatch_fault\n";
    $output .= "            name: Cell Count Mismatch/Fault\n";
    $output .= "          - entity: " . $entity_prefix . "temperature_sensor_fault\n";
    $output .= "            name: Temperature Sensor Fault\n";
    $output .= "          - entity: " . $entity_prefix . "discharge_mos_fault\n";
    $output .= "            name: Discharge MOS Fault\n";
    $output .= "          - entity: " . $entity_prefix . "charge_mos_fault\n";
    $output .= "            name: Charge MOS Fault\n";
    $output .= "          - entity: " . $entity_prefix . "reverse_connected_alert\n";
    $output .= "            name: Reverse Connected Alert\n";
  }
  return $output;
}

function total_entities($device_name, $bms_type) {
  $output = "";
  $output .= "      - type: entities\n";
  $output .= "        state_color: true\n";
  $output .= "        view_layout:\n";
  $output .= "          position: sidebar\n";
  $output .= "        title: System Overview\n";
  $output .= "        entities:\n";
  $output .= "          - entity: sensor." . $device_name . "_total_current\n";
  $output .= "            name: Total Current\n";
  $output .= "          - entity: sensor." . $device_name . "_total_power\n";
  $output .= "            name: Total Power\n";
  $output .= "          - entity: sensor." . $device_name . "_total_voltage\n";
  $output .= "            name: Total Voltage\n";
  $output .= "          - entity: sensor." . $device_name . "_total_soc\n";
  $output .= "            name: Total SOC\n";
  $output .= "          - entity: sensor." . $device_name . "_total_remaining_capacity\n";
  $output .= "            name: Total Remain Capacity\n";
  $output .= "          - entity: sensor." . $device_name . "_total_full_capacity\n";
  $output .= "            name: Total Full Capacity\n";
  $output .= "          - entity: sensor." . $device_name . "_max_cell_voltage\n";
  $output .= "            name: Total Cell Voltage Max\n";
  $output .= "          - entity: sensor." . $device_name . "_min_cell_voltage\n";
  $output .= "            name: Total Cell Voltage Min\n";
  $output .= "          - entity: sensor." . $device_name . "_cell_voltage_delta\n";
  $output .= "            name: Total Cell Voltage Diff\n";
  $output .= "          - entity: sensor." . $device_name . "_packs_count\n";
  $output .= "            name: Total Packs Number\n";
  return $output;
}

function pack_entities($device_name, $total_packs_num, $bms_type, $jk_display_index_start = '01') {
  $output = "";
  for ($i = 0; $i < $total_packs_num; $i++) {
    $display_i = ($bms_type == 'JK_PB' && ($jk_display_index_start == '00' || $jk_display_index_start == '0')) ? $i : $i + 1;
    $pack_str = "pack_" . sprintf("%02d", $display_i);
    
    $output .= "      - type: vertical-stack\n";
    $output .= "        cards:\n";
    
    // 1. Glance Card for live metrics
    $output .= "          - type: glance\n";
    $output .= "            title: Pack " . sprintf("%02d", $display_i) . " Overview\n";
    $output .= "            entities:\n";
    
    $sensor_prefix = "sensor." . $device_name . "_" . $pack_str . "_";
    
    $output .= "              - entity: " . $sensor_prefix . "soc\n";
    $output .= "                name: SOC\n";
    $output .= "              - entity: " . $sensor_prefix . "voltage\n";
    $output .= "                name: Voltage\n";
    $output .= "              - entity: " . $sensor_prefix . "current\n";
    $output .= "                name: Current\n";
    $output .= "              - entity: " . $sensor_prefix . "power\n";
    $output .= "                name: Power\n";
    $output .= "              - entity: " . $sensor_prefix . "soh\n";
    $output .= "                name: SOH\n";
    $output .= "              - entity: " . $sensor_prefix . "cycle_count\n";
    $output .= "                name: Cycles\n";
    if ($bms_type == 'JK_PB') {
      $output .= "              - entity: " . $sensor_prefix . "balance_current\n";
      $output .= "                name: Balance Current\n";
    }
    $columns = ($bms_type == 'JK_PB') ? 7 : 6;
    $output .= "            columns: " . $columns . "\n";
    
    // 2. Grid card for details (multi-column)
    $output .= "          - type: grid\n";
    $output .= "            title: Pack " . sprintf("%02d", $display_i) . " Details\n";
    $output .= "            columns: 2\n";
    $output .= "            square: false\n";
    $output .= "            cards:\n";
    
    // Column 1: Capacity
    $output .= "              - type: entities\n";
    $output .= "                title: Capacity\n";
    $output .= "                entities:\n";
    $output .= "                  - entity: " . $sensor_prefix . "remaining_capacity\n";
    $output .= "                    name: Remain Capacity\n";
    $output .= "                  - entity: " . $sensor_prefix . "full_capacity\n";
    $output .= "                    name: Full Capacity\n";
    
    // Column 2: Switches & Status
    $binary_prefix = "binary_sensor." . $device_name . "_" . $pack_str . "_";
    $output .= "              - type: entities\n";
    $output .= "                title: Switches & Status\n";
    $output .= "                entities:\n";
    $output .= "                  - entity: " . $binary_prefix . "charge_enabled_status\n";
    $output .= "                    name: Charge Switch Active\n";
    $output .= "                  - entity: " . $binary_prefix . "discharge_enabled_status\n";
    $output .= "                    name: Discharge Switch Active\n";
    $output .= "                  - entity: " . $binary_prefix . "heating_switch_active\n";
    $output .= "                    name: Heating Switch Active\n";
    $output .= "                  - entity: " . $binary_prefix . "charger_available\n";
    $output .= "                    name: Charger Available\n";
    $output .= "                  - entity: " . $binary_prefix . "current_limiter_active\n";
    $output .= "                    name: Current Limiter Active\n";
    $output .= "                  - entity: " . $binary_prefix . "reverse_connected_alert\n";
    $output .= "                    name: Reverse Connected Alert\n";
  }
  return $output;
}

function pack_cell_history($device_name, $total_packs_num, $num_cells, $bms_type, $jk_display_index_start = '01') {
  $output = "";
  for ($i = 0; $i < $total_packs_num; $i++) {
    $display_i = ($bms_type == 'JK_PB' && ($jk_display_index_start == '00' || $jk_display_index_start == '0')) ? $i : $i + 1;
    $pack_str = "pack_" . sprintf("%02d", $display_i);
    $output .= "      - title: Pack " . sprintf("%02d", $display_i) . " Cell Voltages\n";
    $output .= "        type: history-graph\n";
    $output .= "        hours_to_show: 48\n";
    $output .= "        min_y_axis: 2000\n";
    $output .= "        max_y_axis: 4000\n";
    $output .= "        fit_y_data: false\n";
    $output .= "        entities:\n";
    for ($j = 1; $j <= $num_cells; $j++) {
      $output .= "          - entity: sensor." . $device_name . "_" . $pack_str . "_cell_" . sprintf("%02d", $j) . "_voltage\n";
      $output .= "            name: Cell" . sprintf("%02d", $j) . "\n";
    }
  }
  return $output;
}

function pack_temp_history($device_name, $total_packs_num, $num_temps, $bms_type, $jk_display_index_start = '01') {
  $output = "";
  for ($i = 0; $i < $total_packs_num; $i++) {
    $display_i = ($bms_type == 'JK_PB' && ($jk_display_index_start == '00' || $jk_display_index_start == '0')) ? $i : $i + 1;
    $pack_str = "pack_" . sprintf("%02d", $display_i);
    $output .= "      - title: Pack " . sprintf("%02d", $display_i) . " Temperatures\n";
    $output .= "        type: history-graph\n";
    $output .= "        hours_to_show: 48\n";
    $output .= "        entities:\n";
    
    for ($j = 1; $j <= $num_temps; $j++) {
      $output .= "          - entity: sensor." . $device_name . "_" . $pack_str . "_temperature_" . sprintf("%02d", $j) . "\n";
      $output .= "            name: Temp " . sprintf("%02d", $j) . "\n";
    }
  }
  return $output;
}

function generate_dashboard_template($device_name, $total_packs_num, $num_cells, $num_temps, $bms_type, $jk_display_index_start = '01') {
    $output = views($bms_type);
    $output .= glance($device_name, $bms_type);
    $output .= pack_warn_entity_filter($device_name, $total_packs_num, $bms_type, $jk_display_index_start);
    $output .= total_entities($device_name, $bms_type);
    $output .= pack_entities($device_name, $total_packs_num, $bms_type, $jk_display_index_start);
    $output .= pack_cell_history($device_name, $total_packs_num, $num_cells, $bms_type, $jk_display_index_start);
    $output .= pack_temp_history($device_name, $total_packs_num, $num_temps, $bms_type, $jk_display_index_start);

    $output = str_replace(" ", "&nbsp;", $output);

    return $output;
}

if (isset($_GET['device_name'])) {

  $device_name = $_GET['device_name'];
  $total_packs_num = $_GET['total_packs_num'];
  $num_cells = $_GET['num_cells'];
  $num_temps = $_GET['num_temps'];
  $bms_type = isset($_GET['bms_type']) ? $_GET['bms_type'] : 'PACE_LV';
  $jk_display_index_start = isset($_GET['jk_display_index_start']) ? $_GET['jk_display_index_start'] : '01';

  $device_name = strtolower(str_replace(" ", "_", $device_name));
}

?>

<style>
  #yaml_codes {
    white-space: pre-wrap;
    background-color: #111;
    color: #fff;
    font-family: monospace;
    padding: 10px;
    position: relative;
  }
  #copy_button {
    padding: 10px;
    cursor: pointer;
    float: text;
    background: #ddd;
    margin-right: 10px;
  }

  .yaml_title{
    background-color: #555;
    text-align: right;
    line-height: 50px;
    height: 50px;
    margin-top: 30px;
  }

  .form_ctn {
    padding: 10px 10px 50px 10px;
    max-width: 300px;
    margin: auto;
  }

  .form_ctn input, .form_ctn select {
    display: block;
    margin-top: 10px;
    width: 100%;
    box-sizing: border-box;
  }
  .form_ctn small {
    display: block;
    color: #888;
    font-size: 11px;
    margin-top: 2px;
    margin-bottom: 5px;
    line-height: 1.2;
  }
  .cssButton {
    margin-top: 20px!important;
  }
</style>

<link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/highlight.js/11.5.1/styles/default.min.css">
<script src="https://cdnjs.cloudflare.com/ajax/libs/highlight.js/11.5.1/highlight.min.js"></script>

<div class="form_ctn">
  <form action="">
    <input type="text" name="device_name" placeholder="Device Name" class="input_box" value="<?php echo isset($_GET['device_name']) ? htmlspecialchars($_GET['device_name']) : 'Gobel Battery'; ?>">
    <small>Device Name: Name of the Integration device (defaults to "Gobel Battery")</small>
    
    <input type="number" name="total_packs_num" placeholder="Total Packs Num" class="input_box" value="<?php echo isset($_GET['total_packs_num']) ? htmlspecialchars($_GET['total_packs_num']) : '1'; ?>">
    <small>Total Packs Num: Number of battery packs in parallel</small>
    
    <input type="number" name="num_cells" placeholder="View Num Cells" class="input_box" value="<?php echo isset($_GET['num_cells']) ? htmlspecialchars($_GET['num_cells']) : '16'; ?>">
    <small>View Num Cells: Number of cells per pack (e.g. 16)</small>
    
    <input type="number" name="num_temps" placeholder="View Num Temps" class="input_box" value="<?php echo isset($_GET['num_temps']) ? htmlspecialchars($_GET['num_temps']) : '4'; ?>">
    <small>View Num Temps: Number of temperature sensors per pack (e.g. 4)</small>
    
    <select name="bms_type" class="input_box" style="margin-top: 10px; height: 35px; background: #fff; border: 1px solid #ccc; padding: 5px;">
      <option value="PACE_LV" <?php if (isset($_GET['bms_type']) && $_GET['bms_type'] == 'PACE_LV') echo 'selected'; ?>>PACE LV BMS (RS232/RS485)</option>
      <option value="PACE_LV_WIFI" <?php if (isset($_GET['bms_type']) && $_GET['bms_type'] == 'PACE_LV_WIFI') echo 'selected'; ?>>PACE LV WIFI BMS</option>
      <option value="JK_PB" <?php if (isset($_GET['bms_type']) && $_GET['bms_type'] == 'JK_PB') echo 'selected'; ?>>JK BMS</option>
      <option value="TDT" <?php if (isset($_GET['bms_type']) && $_GET['bms_type'] == 'TDT') echo 'selected'; ?>>TDT BMS (RS232)</option>
    </select>

    <div id="jk_index_container" style="display: none;">
      <select name="jk_display_index_start" class="input_box" style="margin-top: 10px; height: 35px; background: #fff; border: 1px solid #ccc; padding: 5px;">
        <option value="01" <?php if (isset($_GET['jk_display_index_start']) && $_GET['jk_display_index_start'] == '01') echo 'selected'; ?>>JK Display Index Start: 01</option>
        <option value="00" <?php if (isset($_GET['jk_display_index_start']) && $_GET['jk_display_index_start'] == '00') echo 'selected'; ?>>JK Display Index Start: 00</option>
      </select>
      <small>JK Display Index Start: "00" matches dial-up exactly; "01" shifts index to start from 01.</small>
    </div>

    <input type="submit" name="Generate" class="cssButton button_send">
  </form>
</div>

<script>
  // Toggle JK display index container based on bms_type select selection
  const bmsTypeSelect = document.querySelector('select[name="bms_type"]');
  const jkIndexContainer = document.getElementById('jk_index_container');
  function toggleJkIndex() {
    if (bmsTypeSelect && bmsTypeSelect.value === 'JK_PB') {
      jkIndexContainer.style.display = 'block';
    } else if (jkIndexContainer) {
      jkIndexContainer.style.display = 'none';
    }
  }
  if (bmsTypeSelect && jkIndexContainer) {
    bmsTypeSelect.addEventListener('change', toggleJkIndex);
    toggleJkIndex();
  }
</script>

<?php if (isset($_GET['device_name'])) { ?>

<div class="yaml_title">
  <button id="copy_button">
    Copy Code
  </button>
</div>

<div id="yaml_codes" style="white-space: pre-wrap; background-color: #222; color: #fff; font-family: monospace; padding: 10px;">
  <?php echo generate_dashboard_template($device_name, $total_packs_num, $num_cells, $num_temps, $bms_type, $jk_display_index_start); ?>
</div>

<script>
  // Initialize syntax highlighting
  hljs.highlightElement(document.getElementById('yaml_codes'));

  // Function to handle copy action
  document.getElementById('copy_button').addEventListener('click', function() {
    // Create a temporary textarea to hold the code for copying
    const tempTextArea = document.createElement('textarea');
    
    // Get the text content from the div and replace non-breaking spaces with regular spaces
    const codeText = document.getElementById('yaml_codes').innerText.replace(/\u00A0/g, ' ');
    tempTextArea.value = codeText;
    
    document.body.appendChild(tempTextArea);

    // Select and copy the code
    tempTextArea.select();
    tempTextArea.setSelectionRange(0, 99999); // For mobile devices

    // Execute the copy command
    document.execCommand('copy');

    // Remove the temporary textarea
    document.body.removeChild(tempTextArea);

    // Change button text to "Copied!" to give feedback to the user
    const copyButton = document.getElementById('copy_button');
    copyButton.innerText = 'Copied!';
    
    // Optional: Revert the button text back to "Copy Code" after a few seconds
    setTimeout(function() {
      copyButton.innerText = 'Copy Code';
    }, 2000); // Change text back after 2 seconds
  });
</script>

<?php } ?>
