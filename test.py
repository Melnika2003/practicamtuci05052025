from ultralytics import YOLO
import cv2
model = YOLO('best_truck.pt')
print(model.names)
img = cv2.imread('example/log_centr.jpg')
results = model.predict(img, classes=[17], conf=0.006, verbose=True)
count = len(results[0].boxes) if results and results[0].boxes else 0
detected_classes = results[0].boxes.cls.cpu().numpy().tolist() if results and results[0].boxes.cls is not None else []
print(f"Грузовиков: {count}, классы: {detected_classes}")
annotated_img = results[0].plot()
cv2.imwrite('test_output.jpg', annotated_img)