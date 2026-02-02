import json
import os
import sqlalchemy
from sqlalchemy import Column, Integer, String, Float, ForeignKey, Date, create_engine
from sqlalchemy.orm import relationship, sessionmaker, declarative_base
from datetime import datetime

# Создаем базовый класс для моделей
Base = declarative_base()


# ========== МОДЕЛИ КЛАССОВ ==========

class Publisher(Base):
    __tablename__ = 'publisher'

    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False)

    books = relationship('Book', back_populates='publisher')


class Book(Base):
    __tablename__ = 'book'

    id = Column(Integer, primary_key=True)
    title = Column(String, nullable=False)
    id_publisher = Column(Integer, ForeignKey('publisher.id'), nullable=False)

    publisher = relationship('Publisher', back_populates='books')
    stocks = relationship('Stock', back_populates='book')


class Shop(Base):
    __tablename__ = 'shop'

    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False)

    stocks = relationship('Stock', back_populates='shop')


class Stock(Base):
    __tablename__ = 'stock'

    id = Column(Integer, primary_key=True)
    id_book = Column(Integer, ForeignKey('book.id'), nullable=False)
    id_shop = Column(Integer, ForeignKey('shop.id'), nullable=False)
    count = Column(Integer, nullable=False)

    book = relationship('Book', back_populates='stocks')
    shop = relationship('Shop', back_populates='stocks')
    sales = relationship('Sale', back_populates='stock')


class Sale(Base):
    __tablename__ = 'sale'

    id = Column(Integer, primary_key=True)
    price = Column(Float, nullable=False)
    date_sale = Column(Date, nullable=False)
    id_stock = Column(Integer, ForeignKey('stock.id'), nullable=False)
    count = Column(Integer, nullable=False)

    stock = relationship('Stock', back_populates='sales')


# Функция для создания таблиц
def create_tables(engine):
    Base.metadata.create_all(engine)


# ========== ФУНКЦИЯ ДЛЯ ПОЛУЧЕНИЯ ПРОДАЖ ==========

def get_publisher_sales(session, publisher_input):
    """
    Получает информацию о продажах книг указанного издателя
    """
    try:
        # Пытаемся интерпретировать ввод как ID
        publisher_id = int(publisher_input)
        publisher = session.query(Publisher).filter(Publisher.id == publisher_id).one()
    except (ValueError, sqlalchemy.orm.exc.NoResultFound):
        # Если не число или не найдено по ID, ищем по имени
        try:
            publisher = session.query(Publisher).filter(Publisher.name.ilike(f'%{publisher_input}%')).one()
        except sqlalchemy.orm.exc.NoResultFound:
            return None

    # Формируем запрос
    query = (
        session.query(
            Book.title.label('book_title'),
            Shop.name.label('shop_name'),
            Sale.price,
            Sale.date_sale
        )
        .select_from(Publisher)
        .join(Book, Book.id_publisher == Publisher.id)
        .join(Stock, Stock.id_book == Book.id)
        .join(Shop, Shop.id == Stock.id_shop)
        .join(Sale, Sale.id_stock == Stock.id)
        .filter(Publisher.id == publisher.id)
        .order_by(Sale.date_sale.desc())
    )

    return query.all()


# ========== ОСНОВНАЯ ПРОГРАММА ==========

def main():
    # Настройки подключения к БД
    DSN = "postgresql://postgres:123@localhost:5432/bookstore_db"

    # Создаем движок
    engine = create_engine(DSN)

    # Создаем таблицы
    create_tables(engine)

    # Создаем фабрику сессий
    Session = sessionmaker(bind=engine)
    session = Session()

    print("=" * 60)
    print("СИСТЕМА УЧЕТА ПРОДАЖ КНИГ")
    print("=" * 60)

    # Загрузка тестовых данных
    fixtures_file = 'tests_data.json'
    if os.path.exists(fixtures_file):
        print(f"Загружаем тестовые данные из {fixtures_file}...")
        try:
            with open(fixtures_file, 'r', encoding='utf-8') as fd:
                data = json.load(fd)

            # Словарь для соответствия моделей
            models = {
                'publisher': Publisher,
                'shop': Shop,
                'book': Book,
                'stock': Stock,
                'sale': Sale,
            }

            for record in data:
                model_class = models.get(record['model'])
                if model_class:
                    fields = record.get('fields', {})

                    # Преобразуем дату из строки в объект Date
                    if record['model'] == 'sale' and 'date_sale' in fields:
                        date_str = fields['date_sale']
                        try:
                            # Пробуем разные форматы даты
                            try:
                                date_obj = datetime.strptime(date_str, '%Y-%m-%d').date()
                            except ValueError:
                                try:
                                    date_obj = datetime.strptime(date_str, '%d-%m-%Y').date()
                                except ValueError:
                                    date_obj = datetime.strptime(date_str, '%Y/%m/%d').date()
                            fields['date_sale'] = date_obj
                        except ValueError:
                            print(f"Ошибка парсинга даты: {date_str}")
                            continue

                    # Создаем объект
                    model_obj = model_class(id=record.get('pk'), **fields)
                    session.add(model_obj)

            session.commit()
            print("Тестовые данные успешно загружены!")
        except Exception as e:
            print(f"Ошибка при загрузке тестовых данных: {e}")
            session.rollback()

    print("\n" + "=" * 60)

    # Запрос данных от пользователя
    while True:
        print("\nМЕНЮ:")
        print("1. Найти продажи по издателю")
        print("2. Показать всех издателей")
        print("3. Выйти")

        choice = input("Выберите действие (1-3): ").strip()

        if choice == '1':
            publisher_input = input("Введите имя или ID издателя: ").strip()

            if not publisher_input:
                print("Ошибка: Введите имя или ID издателя")
                continue

            sales = get_publisher_sales(session, publisher_input)

            if sales is None:
                print(f"Издатель '{publisher_input}' не найден.")
                continue

            if not sales:
                print(f"Для издателя '{publisher_input}' нет записей о продажах.")
                continue

            # Вывод результатов
            print("\n" + "=" * 80)
            print(f"ПРОДАЖИ КНИГ ИЗДАТЕЛЯ")
            print("=" * 80)
            print(f"{'Название книги':<30} | {'Магазин':<15} | {'Цена':<10} | {'Дата продажи':<12}")
            print("-" * 80)

            for sale in sales:
                book_title, shop_name, price, date_sale = sale
                # Форматируем дату
                if hasattr(date_sale, 'strftime'):
                    date_str = date_sale.strftime('%d-%m-%Y')
                else:
                    date_str = str(date_sale)

                print(f"{book_title:<30} | {shop_name:<15} | {price:<10.2f} | {date_str:<12}")

            print("=" * 80)

        elif choice == '2':
            # Показать всех издателей
            publishers = session.query(Publisher).order_by(Publisher.id).all()

            if not publishers:
                print("В базе данных нет издателей.")
                continue

            print("\n" + "=" * 40)
            print("СПИСОК ИЗДАТЕЛЕЙ")
            print("=" * 40)
            print(f"{'ID':<5} | {'Имя':<30}")
            print("-" * 40)

            for pub in publishers:
                print(f"{pub.id:<5} | {pub.name:<30}")

            print("=" * 40)
            print(f"Всего издателей: {len(publishers)}")

        elif choice == '3':
            print("Выход из программы...")
            break

        else:
            print("Неверный выбор. Пожалуйста, введите 1, 2 или 3.")


# Запуск программы
if __name__ == "__main__":
    main()