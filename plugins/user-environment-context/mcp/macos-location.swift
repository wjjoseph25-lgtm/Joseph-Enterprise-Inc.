import CoreLocation
import Foundation

final class LocationDelegate: NSObject, CLLocationManagerDelegate {
  private let manager = CLLocationManager()
  private var finished = false

  override init() {
    super.init()
    manager.delegate = self
    manager.desiredAccuracy = kCLLocationAccuracyBest
  }

  func start() {
    if !CLLocationManager.locationServicesEnabled() {
      fail("Location Services are disabled.")
      return
    }

    manager.requestWhenInUseAuthorization()
    manager.requestLocation()

    DispatchQueue.main.asyncAfter(deadline: .now() + 15) {
      self.fail("Timed out waiting for location permission or GPS result.")
    }
  }

  func locationManager(_ manager: CLLocationManager, didUpdateLocations locations: [CLLocation]) {
    guard let location = locations.last else {
      fail("No location returned.")
      return
    }
    let payload: [String: Any] = [
      "latitude": location.coordinate.latitude,
      "longitude": location.coordinate.longitude,
      "accuracy_meters": location.horizontalAccuracy
    ]
    writeLocationFile(payload)
    finish(payload)
  }

  func locationManager(_ manager: CLLocationManager, didFailWithError error: Error) {
    fail(error.localizedDescription)
  }

  func locationManagerDidChangeAuthorization(_ manager: CLLocationManager) {
    switch manager.authorizationStatus {
    case .denied, .restricted:
      fail("Location permission was denied or restricted.")
    case .authorizedAlways, .authorizedWhenInUse:
      manager.requestLocation()
    default:
      break
    }
  }

  private func finish(_ payload: [String: Any]) {
    guard !finished else { return }
    finished = true
    let data = try! JSONSerialization.data(withJSONObject: payload, options: [])
    print(String(data: data, encoding: .utf8)!)
    exit(0)
  }

  private func fail(_ message: String) {
    guard !finished else { return }
    finished = true
    fputs(message + "\n", stderr)
    exit(1)
  }

  private func writeLocationFile(_ payload: [String: Any]) {
    let url = FileManager.default.homeDirectoryForCurrentUser
      .appendingPathComponent(".codex")
      .appendingPathComponent("user-location.json")
    try? FileManager.default.createDirectory(
      at: url.deletingLastPathComponent(),
      withIntermediateDirectories: true
    )
    let enriched = payload.merging([
      "updated_at": ISO8601DateFormatter().string(from: Date()),
      "source": "macos_location_services"
    ]) { current, _ in current }
    if let data = try? JSONSerialization.data(withJSONObject: enriched, options: [.prettyPrinted]) {
      try? data.write(to: url)
    }
  }
}

let delegate = LocationDelegate()
delegate.start()
RunLoop.main.run()
