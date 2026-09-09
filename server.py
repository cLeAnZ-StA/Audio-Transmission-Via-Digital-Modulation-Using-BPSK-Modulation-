from flask import Flask, render_template
from flask_socketio import SocketIO
import numpy as np

app = Flask(__name__)
# Using threading to prevent Windows freezing
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='threading')

@app.route('/')
def index():
    return render_template('index.html')

def simulate_bpsk_channel(audio_data, snr_db=30):
    # Convert audio bytes to bits
    bits = np.unpackbits(np.frombuffer(audio_data, dtype=np.uint8))
    
    # BPSK MATH FIX: Cast to float to prevent uint8 underflow
    symbols = 2.0 * bits.astype(np.float32) - 1.0
    
    # AWGN Noise Generation
    snr_linear = 10 ** (snr_db / 10.0)
    signal_power = 1.0 
    noise_power = signal_power / snr_linear
    noise = np.sqrt(noise_power) * np.random.randn(len(symbols))
    
    # Channel Transmission
    received_signal = symbols + noise
    
    # Demodulation
    received_bits = (received_signal >= 0).astype(np.uint8)
    
    # Calculate Telemetry
    errors = np.sum(bits != received_bits)
    ber = errors / len(bits) if len(bits) > 0 else 0.0
    
    # Repack to bytes for audio playback
    processed_audio = np.packbits(received_bits).tobytes()
    return processed_audio, ber

@socketio.on('send_audio')
def handle_audio(payload):
    print("[+] Processing audio stream...")
    
    # Extract payload with SNR fallback
    if isinstance(payload, dict):
        audio_bytes = payload.get('audio')
        mime_type = payload.get('mimeType', 'audio/webm')
        snr_val = float(payload.get('snr', 30))
    else:
        audio_bytes = payload
        mime_type = 'audio/webm'
        snr_val = 30.0
        
    socketio.emit('log', {'msg': f"Received {len(audio_bytes)} bytes. Format: {mime_type}."})
    
    # Run the BPSK Simulation
    processed_audio, ber = simulate_bpsk_channel(audio_bytes, snr_db=snr_val)
    
    socketio.emit('log', {'msg': f"BPSK Modulation applied. Channel SNR: {snr_val}dB"})
    socketio.emit('log', {'msg': f"Demodulated with BER: {ber:.6f}"})
    print(f"Channel Telemetry - BER: {ber:.6f}")
    
    # Broadcast telemetry to chart (ignore sender to prevent echo)
    socketio.emit('telemetry', {'ber': float(ber)}, include_self=False)
    
    # Broadcast the audio AND format back to receiver (ignore sender)
    socketio.emit('receive_audio', {
        'audio': processed_audio,
        'mimeType': mime_type
    }, include_self=False)

if __name__ == '__main__':
    print("Starting Communications Node on PORT 5001...")
    socketio.run(app, host='0.0.0.0', port=5001, debug=True)