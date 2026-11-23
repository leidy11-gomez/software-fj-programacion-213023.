"""Sistema de clientes, servicios y reservas de Software FJ.
No usa base de datos: administra la información en listas.
Los errores y eventos se guardan en software_fj.log.
"""
from abc import ABC, abstractmethod
from enum import Enum
import logging
import re

logging.basicConfig(
    filename="software_fj.log",
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
    encoding="utf-8",
)
log = logging.getLogger("SoftwareFJ")


class ErrorSistema(Exception):
    """Error base del sistema."""


class DatoInvalidoError(ErrorSistema):
    """Dato o parámetro inválido."""


class ServicioNoDisponibleError(ErrorSistema):
    """Servicio o recurso no disponible."""


class OperacionNoPermitidaError(ErrorSistema):
    """Operación que no corresponde al estado actual."""


class RecursoNoEncontradoError(ErrorSistema):
    """Cliente, servicio o reserva inexistente."""


class Entidad(ABC):
    def __init__(self, identificador):
        if not str(identificador).strip():
            raise DatoInvalidoError("El identificador es obligatorio.")
        self._identificador = str(identificador).strip()

    @property
    def identificador(self):
        return self._identificador

    @abstractmethod
    def describir(self):
        pass


class Cliente(Entidad):
    def __init__(self, identificador, nombre, correo, telefono):
        super().__init__(identificador)
        self._nombre = str(nombre).strip()
        self._correo = str(correo).strip().lower()
        self._telefono = str(telefono).strip()

        if len(self._nombre) < 2:
            raise DatoInvalidoError("El nombre debe tener al menos 2 letras.")
        if not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", self._correo):
            raise DatoInvalidoError("El correo no tiene un formato válido.")
        if not re.fullmatch(r"\+?\d{7,15}", self._telefono):
            raise DatoInvalidoError("El teléfono debe tener de 7 a 15 dígitos.")

    @property
    def nombre(self):
        return self._nombre

    def describir(self):
        return f"Cliente {self.identificador}: {self.nombre} ({self._correo})"


class Servicio(Entidad, ABC):
    def __init__(self, identificador, nombre, tarifa, activo=True):
        super().__init__(identificador)
        if not str(nombre).strip():
            raise DatoInvalidoError("El nombre del servicio es obligatorio.")
        if not isinstance(tarifa, (int, float)) or tarifa <= 0:
            raise DatoInvalidoError("La tarifa debe ser positiva.")
        self.nombre = str(nombre).strip()
        self.tarifa = float(tarifa)
        self.activo = activo

    def validar(self, duracion):
        if not self.activo:
            raise ServicioNoDisponibleError(f"{self.nombre} está inactivo.")
        if not isinstance(duracion, (int, float)) or isinstance(duracion, bool) or duracion <= 0:
            raise DatoInvalidoError("La duración debe ser un número mayor que cero.")

    def total(self, subtotal, impuesto, descuento):
        if not 0 <= impuesto <= 1 or not 0 <= descuento <= 1:
            raise DatoInvalidoError("Impuesto y descuento deben estar entre 0 y 1.")
        return round(subtotal * (1 - descuento) * (1 + impuesto), 2)

    @abstractmethod
    def calcular_costo(self, duracion, impuesto=0.19, descuento=0, **datos):
        pass

    @abstractmethod
    def describir(self):
        pass


class ReservaSala(Servicio):
    def __init__(self, identificador, nombre, tarifa_hora, capacidad):
        super().__init__(identificador, nombre, tarifa_hora)
        if not isinstance(capacidad, int) or capacidad <= 0:
            raise DatoInvalidoError("La capacidad debe ser un entero positivo.")
        self.capacidad = capacidad

    def validar_solicitud(self, duracion, asistentes=1):
        self.validar(duracion)
        if not isinstance(asistentes, int) or asistentes <= 0:
            raise DatoInvalidoError("Indique una cantidad válida de asistentes.")
        if asistentes > self.capacidad:
            raise DatoInvalidoError("La cantidad supera la capacidad de la sala.")

    def calcular_costo(self, duracion, impuesto=0.19, descuento=0, **datos):
        self.validar_solicitud(duracion, datos.get("asistentes", 1))
        return self.total(self.tarifa * duracion, impuesto, descuento)

    def describir(self):
        return f"Sala {self.nombre}, capacidad {self.capacidad}; tarifa por hora ${self.tarifa:,.0f}."


class AlquilerEquipo(Servicio):
    def __init__(self, identificador, nombre, tarifa_dia, unidades):
        super().__init__(identificador, nombre, tarifa_dia)
        if not isinstance(unidades, int) or unidades < 0:
            raise DatoInvalidoError("Las unidades disponibles deben ser un entero no negativo.")
        self.unidades = unidades

    def validar_solicitud(self, duracion, cantidad=1):
        self.validar(duracion)
        if not isinstance(cantidad, int) or cantidad <= 0:
            raise DatoInvalidoError("La cantidad de equipos debe ser positiva.")
        if cantidad > self.unidades:
            raise ServicioNoDisponibleError("No hay suficientes equipos disponibles.")

    def calcular_costo(self, duracion, impuesto=0.19, descuento=0, **datos):
        cantidad = datos.get("cantidad", 1)
        self.validar_solicitud(duracion, cantidad)
        return self.total(self.tarifa * duracion * cantidad, impuesto, descuento)

    def describir(self):
        return f"Alquiler de {self.nombre}: {self.unidades} disponibles; tarifa diaria ${self.tarifa:,.0f}."


class Asesoria(Servicio):
    def __init__(self, identificador, nombre, tarifa_hora, especialidad):
        super().__init__(identificador, nombre, tarifa_hora)
        if not str(especialidad).strip():
            raise DatoInvalidoError("La especialidad es obligatoria.")
        self.especialidad = especialidad

    def calcular_costo(self, duracion, impuesto=0.19, descuento=0, **datos):
        self.validar(duracion)
        if duracion > 8:
            raise DatoInvalidoError("La asesoría no puede superar 8 horas.")
        if not str(datos.get("consultor", "")).strip():
            raise DatoInvalidoError("Debe indicar el nombre del consultor.")
        return self.total(self.tarifa * duracion, impuesto, descuento)

    def describir(self):
        return f"Asesoría especializada en {self.especialidad}; tarifa por hora ${self.tarifa:,.0f}."


class EstadoReserva(Enum):
    PENDIENTE = "pendiente"
    CONFIRMADA = "confirmada"
    CANCELADA = "cancelada"
    PROCESADA = "procesada"


class Reserva(Entidad):
    def __init__(self, identificador, cliente, servicio, duracion, datos=None):
        super().__init__(identificador)
        if not isinstance(cliente, Cliente) or not isinstance(servicio, Servicio):
            raise DatoInvalidoError("Se requiere un cliente y servicio válidos.")
        self.cliente = cliente
        self.servicio = servicio
        self.duracion = duracion
        self.datos = datos or {}
        self.estado = EstadoReserva.PENDIENTE
        self.costo = None

    def confirmar(self):
        if self.estado != EstadoReserva.PENDIENTE:
            raise OperacionNoPermitidaError("Solo se confirma una reserva pendiente.")
        try:
            self.costo = self.servicio.calcular_costo(self.duracion, **self.datos)
        except ErrorSistema as error:
            log.exception("Error al confirmar reserva %s", self.identificador)
            raise ErrorSistema("No fue posible confirmar la reserva.") from error
        self.estado = EstadoReserva.CONFIRMADA
        log.info("Reserva %s confirmada por $%.2f", self.identificador, self.costo)

    def cancelar(self):
        if self.estado not in (EstadoReserva.PENDIENTE, EstadoReserva.CONFIRMADA):
            raise OperacionNoPermitidaError("No se puede cancelar en este estado.")
        self.estado = EstadoReserva.CANCELADA
        log.info("Reserva %s cancelada", self.identificador)

    def procesar(self):
        if self.estado != EstadoReserva.CONFIRMADA:
            raise OperacionNoPermitidaError("Solo se procesa una reserva confirmada.")
        self.estado = EstadoReserva.PROCESADA
        log.info("Reserva %s procesada", self.identificador)

    def describir(self):
        valor = f"${self.costo:,.2f}" if self.costo is not None else "sin calcular"
        return f"{self.identificador} | {self.cliente.nombre} | {self.servicio.nombre} | {self.estado.value} | {valor}"


class Sistema:
    def __init__(self):
        self.clientes = []
        self.servicios = []
        self.reservas = []

    def registrar_cliente(self, cliente):
        if any(c.identificador == cliente.identificador for c in self.clientes):
            raise DatoInvalidoError("Ese cliente ya está registrado.")
        self.clientes.append(cliente)
        log.info("Cliente %s registrado", cliente.identificador)

    def agregar_servicio(self, servicio):
        if any(s.identificador == servicio.identificador for s in self.servicios):
            raise DatoInvalidoError("Ese servicio ya está registrado.")
        self.servicios.append(servicio)
        log.info("Servicio %s agregado", servicio.identificador)

    def crear_reserva(self, id_reserva, id_cliente, id_servicio, duracion, datos=None):
        try:
            cliente = next(c for c in self.clientes if c.identificador == id_cliente)
            servicio = next(s for s in self.servicios if s.identificador == id_servicio)
        except StopIteration as error:
            raise RecursoNoEncontradoError("Cliente o servicio no encontrado.") from error
        reserva = Reserva(id_reserva, cliente, servicio, duracion, datos)
        self.reservas.append(reserva)
        log.info("Reserva %s creada", id_reserva)
        return reserva


def demostrar():
    sistema = Sistema()

    # Operaciones 1 y 2: cliente válido e inválido.
    try:
        ana = Cliente("C1", "Ana Gómez", "ana@correo.com", "3001234567")
        sistema.registrar_cliente(ana)
        print("1. Cliente válido registrado.")
    except ErrorSistema as e:
        log.exception("Operación 1: %s", e)
        print("Error:", e)

    try:
        Cliente("C2", "Luis", "correo-invalido", "123")
    except ErrorSistema as e:
        log.exception("Operación 2: %s", e)
        print("2. Error esperado de cliente:", e)

    # Operaciones 3 y 4: crear servicios válido e inválido.
    try:
        sistema.agregar_servicio(ReservaSala("S1", "Sala Roble", 50000, 12))
        print("3. Sala creada.")
    except ErrorSistema as e:
        log.exception("Operación 3: %s", e)

    try:
        AlquilerEquipo("S2", "Proyector", 80000, -1)
    except ErrorSistema as e:
        log.exception("Operación 4: %s", e)
        print("4. Error esperado de servicio:", e)

    sistema.agregar_servicio(AlquilerEquipo("S3", "Portátil", 60000, 4))
    sistema.agregar_servicio(Asesoria("S4", "Asesoría TI", 90000, "tecnología"))

    # Operaciones 5 y 6: reserva correcta y aforo excedido.
    r1 = sistema.crear_reserva("R1", "C1", "S1", 2, {"asistentes": 8})
    r1.confirmar()
    print("5.", r1.describir())

    try:
        sistema.crear_reserva("R2", "C1", "S1", 1, {"asistentes": 20}).confirmar()
    except ErrorSistema as e:
        log.exception("Operación 6: %s", e)
        print("6. Error esperado de aforo:", e)

    # Operaciones 7 y 8: alquiler válido y falta de unidades.
    r3 = sistema.crear_reserva("R3", "C1", "S3", 3, {"cantidad": 2})
    r3.confirmar()
    print("7.", r3.describir())

    try:
        sistema.crear_reserva("R4", "C1", "S3", 1, {"cantidad": 10}).confirmar()
    except ErrorSistema as e:
        log.exception("Operación 8: %s", e)
        print("8. Error esperado de inventario:", e)

    # Operaciones 9 y 10: asesoría válida y parámetro faltante.
    r5 = sistema.crear_reserva("R5", "C1", "S4", 1.5, {"consultor": "Laura"})
    r5.confirmar()
    print("9.", r5.describir())

    try:
        sistema.crear_reserva("R6", "C1", "S4", 1, {}).confirmar()
    except ErrorSistema as e:
        log.exception("Operación 10: %s", e)
        print("10. Error esperado de parámetro:", e)

    # Variantes del cálculo con impuesto y descuento opcionales.
    sala = sistema.servicios[0]
    print("Costo normal:", sala.calcular_costo(1, asistentes=4))
    print("Costo con descuento:", sala.calcular_costo(
        1, impuesto=0.19, descuento=0.15, asistentes=4))

    r1.cancelar()
    r3.procesar()

    try:
        r1.procesar()
    except OperacionNoPermitidaError as e:
        log.exception("Operación no permitida: %s", e)
        print("Error esperado de estado:", e)

    try:
        for reserva in sistema.reservas:
            print(reserva.describir())
    except Exception as e:
        log.exception("Error al mostrar reservas: %s", e)
    else:
        log.info("Resumen mostrado correctamente")
    finally:
        print("Demostración terminada. Revisa software_fj.log para los eventos y errores.")


if __name__ == "__main__":
    try:
        demostrar()
    except Exception as e:
        log.exception("Error general no previsto: %s", e)
        print("El sistema controló un error inesperado:", e)
