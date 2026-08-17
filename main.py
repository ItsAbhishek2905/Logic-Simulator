import re
from collections import deque, defaultdict

class VHDLLogicSimulator:
    def __init__(self):
        self.gates = {}
        self.inputs = {}
        self.outputs = {}
        self.wires = {}
        self.levels = defaultdict(list)
        self.level_order = []
    
    def read_vhdl_file(self, filename):
        with open(filename, 'r') as file:
            vhdl_code = file.read()
        self.parse_vhdl_netlist(vhdl_code)
    
    def parse_vhdl_netlist(self, vhdl_code):
        vhdl_code = re.sub(r'--.*', '', vhdl_code)
        
        entity_match = re.search(r'entity\s+\w+\s+is.*?port\s*\((.*?)\);.*?end', vhdl_code, re.IGNORECASE | re.DOTALL)
        if entity_match:
            port_content = entity_match.group(1)
            self._parse_entity_ports(port_content)
        
        arch_match = re.search(r'architecture\s+\w+\s+of\s+\w+\s+is(.*?)begin(.*?)end', vhdl_code, re.IGNORECASE | re.DOTALL)
        if arch_match:
            decl_content = arch_match.group(1)
            body_content = arch_match.group(2)
            self._parse_declarative_part(decl_content)
            self._parse_architecture_body(body_content)
        
        self._auto_detect_ports()
    
    def _parse_entity_ports(self, port_content):

        port_content = re.sub(r'\s+', ' ', port_content)
        
        individual_pattern = r'(\w+(?:\s*,\s*\w+)*)\s*:\s*(in|out)\s+std_logic'
        matches = re.findall(individual_pattern, port_content, re.IGNORECASE)
        
        for signals, nature in matches:
            signal_list = [s.strip() for s in signals.split(',')]
            for signal_name in signal_list:
                if nature.lower() == 'in':
                    self.inputs[signal_name] = 0
                    self.wires[signal_name] = 0
                else:
                    self.outputs[signal_name] = 0
                    self.wires[signal_name] = 0
    
    def _auto_detect_ports(self):
       
        all_wires = set()
        for gate_info in self.gates.values():
            all_wires.update(gate_info['inputs'])
            all_wires.add(gate_info['output'])
        
        driven_wires = set(gate_info['output'] for gate_info in self.gates.values())
        
        for wire in all_wires:
            if wire not in driven_wires and wire not in self.inputs:
                self.inputs[wire] = 0
                if wire not in self.wires:
                    self.wires[wire] = 0
        
        for wire in driven_wires:
            is_used_as_input = any(wire in gate_info['inputs'] for gate_info in self.gates.values())
            if not is_used_as_input and wire not in self.outputs:
                self.outputs[wire] = 0
                if wire not in self.wires:
                    self.wires[wire] = 0
    
    def _parse_declarative_part(self, decl_content):

        signal_matches = re.findall(r'signal\s+(\w+)\s*:\s*std_logic', decl_content, re.IGNORECASE)
        for signal_name in signal_matches:
            if signal_name not in self.wires:
                self.wires[signal_name] = 0
    
    def _parse_architecture_body(self, body_content):

        instantiations = re.finditer(r'(\w+)\s*:\s*(\w+)\s+port\s+map\s*\((.*?)\);', body_content, re.IGNORECASE)
        
        for match in instantiations:
            instance_name, component_name, port_map_content = match.groups()
            
            port_map_content = re.sub(r'\s+', ' ', port_map_content.strip())
            connections = [conn.strip() for conn in port_map_content.split(',')]
            
            gate_type = self._map_component_to_gate(component_name)
            expected_ports = 2 if gate_type == 'NOT' else 3
            
            if len(connections) >= expected_ports:
                if expected_ports == 2:
                    input_wires = connections[:1]
                    output_wire = connections[1]
                else:
                    input_wires = connections[:expected_ports-1]
                    output_wire = connections[expected_ports-1]
                
                if output_wire not in self.wires:
                    self.wires[output_wire] = 0
                for input_wire in input_wires:
                    if input_wire not in self.wires:
                        self.wires[input_wire] = 0
                
                self.gates[instance_name] = {
                    'type': gate_type,
                    'output': output_wire,
                    'inputs': input_wires,
                    'level': -1
                }
    
    def _map_component_to_gate(self, component_name):
        
        component_lower = component_name.lower()
        
        if component_lower in ['or_2', 'or2']:
            return 'OR'
        elif component_lower in ['and_2', 'and2']:
            return 'AND'
        elif component_lower in ['xor_2', 'xor2']:
            return 'XOR'
        elif component_lower in ['nand_2', 'nand2']:
            return 'NAND'
        elif component_lower in ['nor_2', 'nor2']:
            return 'NOR'
        elif component_lower in ['not_1', 'not', 'inverter']:
            return 'NOT'
        elif component_lower in ['buf', 'buffer']:
            return 'BUF'
        else:
            return component_name.upper()
    
    def levelize_circuit(self):
      
        if not self.wires:
            return
            
        graph = {}
        num_inp = {}
        
        for wire in self.wires:
            graph[wire] = []
            num_inp[wire] = 0
        
        for gate_info in self.gates.values():
            output_wire = gate_info['output']
            for input_wire in gate_info['inputs']:
                if input_wire in graph:
                    graph[input_wire].append(output_wire)
                    num_inp[output_wire] += 1
        
        queue = deque()
        
        for wire in self.wires:
            if num_inp[wire] == 0 and wire in self.inputs:
                queue.append(wire)
                self.levels[0].append(wire)
        
        level = 0
        while queue:
            level += 1
            next_queue = deque()
            
            while queue:
                current_wire = queue.popleft()
                if current_wire in graph:
                    for dependent_wire in graph[current_wire]:
                        num_inp[dependent_wire] -= 1
                        if num_inp[dependent_wire] == 0:
                            next_queue.append(dependent_wire)
                            self.levels[level].append(dependent_wire)
            
            queue = next_queue
        
        self.level_order = sorted(self.levels.keys())
        
        for gate_info in self.gates.values():
            output_wire = gate_info['output']
            for level_num, wires in self.levels.items():
                if output_wire in wires:
                    gate_info['level'] = level_num
                    break
    
    def display_circuit_info(self):
        
        print(f"INPUT PORTS ({len(self.inputs)}):")
        print(f"  {', '.join(sorted(self.inputs.keys()))}")
        
        print(f"\nOUTPUT PORTS ({len(self.outputs)}):")
        print(f"  {', '.join(sorted(self.outputs.keys()))}")
        
        print(f"\nCIRCUIT LEVELS ({len(self.level_order)} levels):")
        for level in self.level_order:
            gates_in_level = [gate for gate, info in self.gates.items() if info['level'] == level]
            wires_in_level = self.levels[level]
            
            print(f"\nLevel {level}:")
            print(f"  Wires: {', '.join(wires_in_level)}")
            if gates_in_level:
                print(f"  Gates ({len(gates_in_level)}):")
                for gate in gates_in_level:
                    gate_info = self.gates[gate]
                    print(f"    {gate}: {gate_info['type']} -> {gate_info['output']} = f({gate_info['inputs']})")
            else:
                print("  (Primary inputs - no gates)")
        
        print("-"*60)
    
    def simulate_gate(self, gate_type, inputs):

        if gate_type in ['AND', 'NAND']:
            result = 1
            for inp in inputs:
                result &= inp
            return result if gate_type == 'AND' else 1 - result
        elif gate_type in ['OR', 'NOR']:
            result = 0
            for inp in inputs:
                result |= inp
            return result if gate_type == 'OR' else 1 - result
        elif gate_type in ['XOR', 'XNOR']:
            result = 0
            for inp in inputs:
                result ^= inp
            return result if gate_type == 'XOR' else 1 - result
        elif gate_type == 'NOT':
            return 1 - inputs[0]
        elif gate_type == 'BUF':
            return inputs[0]
        else:
            result = 1
            for inp in inputs:
                result &= inp
            return result
    
    def simulate_level(self, level):

        for wire in self.levels[level]:
            for gate_info in self.gates.values():
                if gate_info['output'] == wire:
                    input_values = []
                    for inp_wire in gate_info['inputs']:
                        input_values.append(self.wires.get(inp_wire, 0))
                    
                    result = self.simulate_gate(gate_info['type'], input_values)
                    self.wires[wire] = result
                    
                    if wire in self.outputs:
                        self.outputs[wire] = result
    
    def simulate(self, simulation_vector):

        self.reset()
        
        print(f"\nSIMULATION INPUT: {simulation_vector}")
    
        for input_name, value in simulation_vector.items():
            if input_name in self.inputs:
                self.inputs[input_name] = value
                self.wires[input_name] = value
            else:
                print(f"Warning: Input '{input_name}' not found")
        
        print("\nSIMULATION PROGRESS:")
        print("-" * 40)
        
        for level in self.level_order:
            print(f"Level {level}:")
            self.simulate_level(level)
            
            for wire in self.levels[level]:
                print(f"  {wire} = {self.wires[wire]}")
        
        print("-" * 40)
        print("SIMULATION COMPLETED")
        
        return self.outputs.copy()
    
    def reset(self):
        """Reset all wire values"""
        for wire in self.wires:
            self.wires[wire] = 0
        for inp in self.inputs:
            self.inputs[inp] = 0
        for out in self.outputs:
            self.outputs[out] = 0

def main():
    
    import sys
    
    if len(sys.argv) < 2:
        print("python simulator.py <vhdl_file.vhd>")
        sys.exit(1)
    
    filename = sys.argv[1]
    
    simulator = VHDLLogicSimulator()
    simulator.read_vhdl_file(filename)
    simulator.levelize_circuit()
    

    simulator.display_circuit_info()
    
    while True:
        user_input = input("\nEnter input values (e.g., i0=1,i1=0) or 'quit': ")
        if user_input.lower() == 'quit':
            break
        
        try:
            input_vector = {}
            pairs = user_input.split(',')
            for pair in pairs:
                key, value = pair.split('=')
                input_vector[key.strip()] = int(value.strip())
            
       
            result = simulator.simulate(input_vector)
            print(f"\nFINAL OUTPUT: {result}")
            
        except Exception as e:
            print(f"Error: {e}")
            print("Please use format: input_name=value,input_name=value")

if __name__ == "__main__":
    main()
