import requests
import json

def fetch_weather_data():
    api_url = "https://api.bmkg.go.id/publik/prakiraan-cuaca?adm4=51.71.04.1007"
    try:
        response = requests.get(api_url)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        print(f"ERROR: Gagal mengambil data. {e}")
        return None
    except json.JSONDecodeError:
        print("ERROR: Data bukan format JSON yang valid.")
        return None

def display_weather(data):
    if not data:
        return

    # Location Information
    lokasi = data.get("lokasi", {})
    if lokasi:
        print("=" * 40)
        print("PRAKIRAAN CUACA BMKG")
        print("=" * 40)
        print(f"Desa/Kelurahan : {lokasi.get('desa', 'N/A')}")
        print(f"Kecamatan      : {lokasi.get('kecamatan', 'N/A')}")
        print(f"Kota/Kabupaten : {lokasi.get('kotkab', 'N/A')}")
        print(f"Provinsi       : {lokasi.get('provinsi', 'N/A')}")
        print(f"Koordinat      : {lokasi.get('lat', 'N/A')}, {lokasi.get('lon', 'N/A')}")
        print(f"Timezone       : {lokasi.get('timezone', 'N/A')}")
        print("-" * 40)

    # Weather Forecast Data
    forecast_list = data.get("data", [])
    if forecast_list and "cuaca" in forecast_list[0]:
        cuaca_days = forecast_list[0]["cuaca"]
        for i, daily_forecast in enumerate(cuaca_days):
            print(f"\n[ HARI KE-{i + 1} ]")
            print("-" * 40)
            for forecast in daily_forecast:
                waktu = forecast.get("local_datetime", "N/A")
                desc = forecast.get("weather_desc", "N/A")
                suhu = forecast.get("t", "N/A")
                kelembapan = forecast.get("hu", "N/A")
                kec_angin = forecast.get("ws", "N/A")
                arah_angin = forecast.get("wd", "N/A")
                jarak_pandang = forecast.get("vs_text", "N/A")

                print(f"Jam: {waktu}")
                print(f"Cuaca: {desc} | Suhu: {suhu}°C | Kelembapan: {kelembapan}%")
                print(f"Angin: {kec_angin} km/j dari {arah_angin} | Pandangan: {jarak_pandang}")
                print("-" * 20)
    else:
        print("Struktur data prakiraan cuaca tidak ditemukan.")

if __name__ == "__main__":
    weather_data = fetch_weather_data()
    display_weather(weather_data)
