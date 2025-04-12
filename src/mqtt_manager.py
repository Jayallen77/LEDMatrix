import paho.mqtt.client as mqtt
import json
from typing import Dict, Any, Optional, List, Callable
from queue import Queue
import threading
import time

class MQTTManager:
    def __init__(self, config: Dict[str, Any], display_manager):
        """Initialize MQTT Manager with configuration."""
        self.config = config.get('mqtt', {})
        self.display_manager = display_manager
        self.client = None
        self.connected = False
        self.message_queue = Queue()
        self.subscriptions = {}
        self.last_update = 0
        self.current_messages = {}
        
        # MQTT Configuration
        self.broker = self.config.get('broker', 'localhost')
        self.port = self.config.get('port', 1883)
        self.username = self.config.get('username')
        self.password = self.config.get('password')
        self.client_id = self.config.get('client_id', 'led_matrix')
        
        # Display Configuration
        self.scroll_speed = self.config.get('scroll_speed', 0.1)
        self.message_timeout = self.config.get('message_timeout', 60)
        self.max_messages = self.config.get('max_messages', 5)
        
        # Initialize MQTT client
        self._setup_mqtt()
        
        # Start message processing thread
        self.running = True
        self.process_thread = threading.Thread(target=self._process_messages)
        self.process_thread.daemon = True
        self.process_thread.start()

    def _setup_mqtt(self):
        """Setup MQTT client and callbacks."""
        self.client = mqtt.Client(client_id=self.client_id)
        
        # Set up callbacks
        self.client.on_connect = self._on_connect
        self.client.on_message = self._on_message
        self.client.on_disconnect = self._on_disconnect
        
        # Set up authentication if configured
        if self.username and self.password:
            self.client.username_pw_set(self.username, self.password)
        
        # Set up TLS if configured
        if self.config.get('use_tls', False):
            self.client.tls_set()
    
    def _on_connect(self, client, userdata, flags, rc):
        """Callback for when the client connects to the broker."""
        if rc == 0:
            print("Connected to MQTT broker")
            self.connected = True
            # Subscribe to configured topics
            for topic in self.config.get('topics', []):
                self.subscribe(topic)
        else:
            print(f"Failed to connect to MQTT broker with code: {rc}")
    
    def _on_message(self, client, userdata, message):
        """Callback for when a message is received."""
        try:
            payload = message.payload.decode()
            try:
                # Try to parse as JSON
                payload = json.loads(payload)
            except json.JSONDecodeError:
                # If not JSON, use as plain text
                pass
            
            self.message_queue.put({
                'topic': message.topic,
                'payload': payload,
                'timestamp': time.time()
            })
        except Exception as e:
            print(f"Error processing message: {e}")
    
    def _on_disconnect(self, client, userdata, rc):
        """Callback for when the client disconnects from the broker."""
        print("Disconnected from MQTT broker")
        self.connected = False
        if rc != 0:
            print(f"Unexpected disconnection. Attempting to reconnect...")
            self._reconnect()
    
    def _reconnect(self):
        """Attempt to reconnect to the MQTT broker."""
        while not self.connected and self.running:
            try:
                self.client.connect(self.broker, self.port)
                self.client.loop_start()
                break
            except Exception as e:
                print(f"Reconnection failed: {e}")
                time.sleep(5)
    
    def start(self):
        """Start the MQTT client connection."""
        try:
            self.client.connect(self.broker, self.port)
            self.client.loop_start()
        except Exception as e:
            print(f"Failed to connect to MQTT broker: {e}")
            self._reconnect()
    
    def stop(self):
        """Stop the MQTT client and message processing."""
        self.running = False
        if self.client:
            self.client.loop_stop()
            self.client.disconnect()
    
    def subscribe(self, topic: str, qos: int = 0):
        """Subscribe to an MQTT topic."""
        if self.client:
            self.client.subscribe(topic, qos)
            print(f"Subscribed to topic: {topic}")
    
    def _process_messages(self):
        """Process messages from the queue and update display."""
        while self.running:
            try:
                # Remove expired messages
                current_time = time.time()
                self.current_messages = {
                    topic: msg for topic, msg in self.current_messages.items()
                    if current_time - msg['timestamp'] < self.message_timeout
                }
                
                # Process new messages
                while not self.message_queue.empty():
                    message = self.message_queue.get()
                    self.current_messages[message['topic']] = message
                
                # Update display if we have messages
                if self.current_messages:
                    self._update_display()
                
                time.sleep(0.1)
            except Exception as e:
                print(f"Error in message processing: {e}")
    
    def _update_display(self):
        """Update the LED matrix display with current messages."""
        try:
            # Create a new image for drawing
            image = Image.new('RGB', (self.display_manager.matrix.width, self.display_manager.matrix.height))
            draw = ImageDraw.Draw(image)
            
            # Sort messages by timestamp (newest first)
            messages = sorted(
                self.current_messages.values(),
                key=lambda x: x['timestamp'],
                reverse=True
            )[:self.max_messages]
            
            # Calculate display layout
            section_height = self.display_manager.matrix.height // min(len(messages), self.max_messages)
            
            # Draw each message
            for i, message in enumerate(messages):
                y = i * section_height
                
                # Format message based on type
                if isinstance(message['payload'], dict):
                    display_text = self._format_dict_message(message['payload'])
                else:
                    display_text = str(message['payload'])
                
                # Draw message text
                draw.text((1, y + 1), display_text,
                         font=self.display_manager.small_font,
                         fill=(255, 255, 255))
            
            # Update the display
            self.display_manager.image = image
            self.display_manager.update_display()
            
        except Exception as e:
            print(f"Error updating display: {e}")
    
    def _format_dict_message(self, payload: Dict[str, Any]) -> str:
        """Format a dictionary payload for display."""
        # Handle Home Assistant state messages
        if 'state' in payload:
            return f"{payload.get('state', '')}"
        
        # Handle other dictionary messages
        return json.dumps(payload, separators=(',', ':')) 