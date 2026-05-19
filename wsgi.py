from app import create_app

# Создаем экземпляр приложения один раз при импорте
app = create_app()

if __name__ == "__main__":
    app.run()
